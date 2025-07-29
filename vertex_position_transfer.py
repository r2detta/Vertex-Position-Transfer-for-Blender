bl_info = {
    "name": "Vertex Position Transfer",
    "author": "r2detta",
    "version": (1, 1),
    "blender": (4, 3, 0),
    "location": "View3D > Tools > Vertex Position Transfer",
    "description": "Transfer vertex positions between meshes based on vertex indices",
    "warning": "",
    "doc_url": "",
    "category": "Mesh",
}

import bpy
import bmesh
from bpy.types import Panel, Operator
from bpy.props import PointerProperty, BoolProperty, FloatProperty

class MESH_OT_transfer_vertex_positions(Operator):
    """Transfer vertex positions from source to target based on vertex indices"""
    bl_idname = "mesh.transfer_vertex_positions"
    bl_label = "Transfer Vertex Positions"
    bl_options = {'REGISTER', 'UNDO'}
    

    
    def get_final_vertex_positions(self, obj):
        """Tüm aktif shapekey'lerin etkisini hesaba katarak final vertex pozisyonlarını döndürür"""
        mesh = obj.data
        
        if not obj.data.shape_keys:
            return [v.co.copy() for v in mesh.vertices]
        
        basis = obj.data.shape_keys.key_blocks[0]
        
        final_positions = [basis.data[i].co.copy() for i in range(len(mesh.vertices))]
        
        for kb in obj.data.shape_keys.key_blocks[1:]:
            if kb.value > 0:
                for i in range(len(mesh.vertices)):
                    offset = kb.data[i].co - basis.data[i].co
                    final_positions[i] += offset * kb.value
        
        return final_positions
    
    def execute(self, context):
        scene = context.scene
        vertex_transfer_props = scene.vertex_transfer_props
        
        source_obj = vertex_transfer_props.source_object
        target_obj = vertex_transfer_props.target_object
        
        if not source_obj or not target_obj:
            self.report({'ERROR'}, "Source and target objects must be selected!")
            return {'CANCELLED'}
        
        if source_obj.type != 'MESH' or target_obj.type != 'MESH':
            self.report({'ERROR'}, "Both source and target must be mesh objects!")
            return {'CANCELLED'}
        
        # Gizli object'lerle çalışabilmek için view layer'da görünürlüğü kontrol et
        if source_obj.hide_viewport:
            self.report({'WARNING'}, "Source object is hidden in viewport, but transfer will still work.")
        
        if target_obj.hide_viewport:
            self.report({'WARNING'}, "Target object is hidden in viewport, but transfer will still work.")
        
        # Panel'deki property'leri al
        blend_factor = vertex_transfer_props.blend_factor
        transfer_to_active_shapekey = vertex_transfer_props.transfer_to_active_shapekey
        only_selected_vertices = vertex_transfer_props.only_selected_vertices
        
        # Seçili vertexleri kontrol et
        selected_vertices = set()
        if only_selected_vertices:
            # Gizli object'lerle çalışmak için daha güvenli yöntem
            source_was_hidden = source_obj.hide_viewport
            
            # Önce object modunda seçili vertexleri kontrol et
            try:
                bm = bmesh.new()
                bm.from_mesh(source_obj.data)
                bm.verts.ensure_lookup_table()
                selected_vertices = {v.index for v in bm.verts if v.select}
                bm.free()
                
                if not selected_vertices:
                    # Eğer object modunda seçili vertex yoksa, edit moduna geçmeyi dene
                    if not source_was_hidden:
                        # Sadece görünür object'ler için edit moduna geç
                        original_active = context.view_layer.objects.active
                        original_mode = context.mode
                        
                        context.view_layer.objects.active = source_obj
                        
                        if context.mode != 'EDIT_MESH':
                            bpy.ops.object.mode_set(mode='EDIT')
                        
                        # Edit modunda seçili vertexleri al
                        try:
                            bm = bmesh.from_edit_mesh(source_obj.data)
                            bm.verts.ensure_lookup_table()
                            selected_vertices = {v.index for v in bm.verts if v.select}
                            bm.free()
                        except Exception as e:
                            self.report({'WARNING'}, f"Could not read selected vertices: {str(e)}")
                            selected_vertices = set()
                        
                        # Orijinal duruma geri dön
                        context.view_layer.objects.active = original_active
                        if original_mode != 'EDIT_MESH':
                            bpy.ops.object.mode_set(mode=original_mode)
                    else:
                        self.report({'WARNING'}, "Source object is hidden. Cannot read selected vertices in edit mode.")
                        return {'CANCELLED'}
                
            except Exception as e:
                self.report({'ERROR'}, f"Error reading selected vertices: {str(e)}")
                return {'CANCELLED'}
            
            if not selected_vertices:
                self.report({'WARNING'}, "No vertices selected in source object!")
                return {'CANCELLED'}
            
            self.report({'INFO'}, f"Found {len(selected_vertices)} selected vertices in source object.")
        
        original_active = context.view_layer.objects.active
        original_mode = context.mode
        
        context.view_layer.objects.active = target_obj
        
        if original_mode == 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='OBJECT')
        
        try:
            source_positions = self.get_final_vertex_positions(source_obj)
            
            target_mesh = target_obj.data
            if len(source_positions) > len(target_mesh.vertices):
                self.report({'WARNING'}, f"Source has more vertices ({len(source_positions)}) than target ({len(target_mesh.vertices)})")
            
            successful_transfers = 0
            
            if target_obj.data.shape_keys and transfer_to_active_shapekey:
                active_key_index = target_obj.active_shape_key_index
                if active_key_index >= 0:
                    active_key = target_obj.data.shape_keys.key_blocks[active_key_index]
                    
                    for i, v in enumerate(active_key.data):
                        if i < len(source_positions):
                            # Sadece seçili vertexleri transfer et
                            if not only_selected_vertices or i in selected_vertices:
                                world_co = source_obj.matrix_world @ source_positions[i]
                                local_co = target_obj.matrix_world.inverted() @ world_co
                                
                                if blend_factor < 1.0:
                                    blended_co = v.co.lerp(local_co, blend_factor)
                                    v.co = blended_co
                                else:
                                    v.co = local_co
                                
                                successful_transfers += 1
                    
                    if only_selected_vertices:
                        self.report({'INFO'}, f"Transferred {len(selected_vertices)} selected vertices to shapekey '{active_key.name}'.")
                    else:
                        self.report({'INFO'}, f"Transferred to shapekey '{active_key.name}': {successful_transfers} vertices.")
                else:
                    self.report({'WARNING'}, "No active shapekey found on target, transferring to base mesh.")
                    self.transfer_to_base_mesh(target_obj, source_obj, source_positions, selected_vertices, blend_factor, only_selected_vertices)
            else:
                self.transfer_to_base_mesh(target_obj, source_obj, source_positions, selected_vertices, blend_factor, only_selected_vertices)
            
            target_mesh.update()
            
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
            
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Error: {str(e)}")
            return {'CANCELLED'}
            
        finally:
            context.view_layer.objects.active = original_active
            if original_mode == 'EDIT_MESH':
                bpy.ops.object.mode_set(mode='EDIT')
    
    def transfer_to_base_mesh(self, target_obj, source_obj, source_positions, selected_vertices, blend_factor, only_selected_vertices):
        """Temel mesh vertexlerine pozisyon transfer et"""
        target_mesh = target_obj.data
        successful_transfers = 0
        
        for i, v in enumerate(target_mesh.vertices):
            if i < len(source_positions):
                # Sadece seçili vertexleri transfer et
                if not only_selected_vertices or i in selected_vertices:
                    world_co = source_obj.matrix_world @ source_positions[i]
                    local_co = target_obj.matrix_world.inverted() @ world_co
                    
                    if blend_factor < 1.0:
                        blended_co = v.co.lerp(local_co, blend_factor)
                        v.co = blended_co
                    else:
                        v.co = local_co
                    
                    successful_transfers += 1
        
        if only_selected_vertices:
            self.report({'INFO'}, f"Transferred {len(selected_vertices)} selected vertices to base mesh.")
        else:
            self.report({'INFO'}, f"Transferred to base mesh: {successful_transfers} vertices.")

class MESH_OT_check_vertex_counts(Operator):
    """Check vertex count compatibility between source and target objects"""
    bl_idname = "mesh.check_vertex_counts"
    bl_label = "Compare Vertex Counts"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        vertex_transfer_props = scene.vertex_transfer_props
        
        source_obj = vertex_transfer_props.source_object
        target_obj = vertex_transfer_props.target_object
        
        if not source_obj or not target_obj:
            self.report({'ERROR'}, "Source and target objects must be selected!")
            return {'CANCELLED'}
        
        if source_obj.type != 'MESH' or target_obj.type != 'MESH':
            self.report({'ERROR'}, "Both source and target must be mesh objects!")
            return {'CANCELLED'}
        
        source_count = len(source_obj.data.vertices)
        target_count = len(target_obj.data.vertices)
        
        if source_count == target_count:
            self.report({'INFO'}, f"Vertex counts match: {source_count}")
        else:
            self.report({'WARNING'}, f"Vertex counts differ: Source: {source_count}, Target: {target_count}")
            
            if source_count > target_count:
                self.report({'WARNING'}, f"⚠ Source has {source_count - target_count} more vertices than target")
            else:
                self.report({'WARNING'}, f"Target has {target_count - source_count} more vertices than source")
        
        return {'FINISHED'}

class MESH_PT_vertex_transfer(Panel):
    """Vertex Position Transfer Panel"""
    bl_label = "Vertex Position Transfer"
    bl_idname = "MESH_PT_vertex_transfer"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Tool"
    bl_context = "objectmode"
    
    @classmethod
    def poll(cls, context):
        return context.mode in {'OBJECT', 'EDIT_MESH'}
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        try:
            vertex_transfer_props = scene.vertex_transfer_props
        except:
            layout.label(text="Error: Properties not found")
            return
        
        layout.label(text="Select Objects:")
        col = layout.column()
        col.prop(vertex_transfer_props, "source_object", text="Source")
        col.prop(vertex_transfer_props, "target_object", text="Target")
        
        box = layout.box()
        box.label(text="Transfer Settings:")
        
        # Properties'leri panel'den al
        row = box.row()
        row.prop(vertex_transfer_props, "blend_factor", slider=True)
        
        row = box.row()
        row.prop(vertex_transfer_props, "transfer_to_active_shapekey")
        
        row = box.row()
        row.prop(vertex_transfer_props, "only_selected_vertices")
        
        # Transfer butonu
        box.operator("mesh.transfer_vertex_positions", text="Transfer Vertex Positions")
        
        layout.operator("mesh.check_vertex_counts", icon='CHECKMARK')
        
        if vertex_transfer_props.target_object:
            sk_create_box = layout.box()
            sk_create_box.label(text="ShapeKey Management:")
            sk_create_box.operator("mesh.create_transfer_shapekey", icon='ADD')
        
        if vertex_transfer_props.source_object and vertex_transfer_props.source_object.data.shape_keys:
            sk_box = layout.box()
            sk_box.label(text="Source ShapeKeys:", icon='SHAPEKEY_DATA')
            for kb in vertex_transfer_props.source_object.data.shape_keys.key_blocks:
                if kb.value > 0:
                    sk_box.label(text=f"{kb.name}: {kb.value:.2f}", icon='KEYTYPE_KEYFRAME_VEC')
        
        if vertex_transfer_props.target_object and vertex_transfer_props.target_object.data.shape_keys:
            sk_box = layout.box()
            sk_box.label(text="Target ShapeKeys:", icon='SHAPEKEY_DATA')
            active_key_index = vertex_transfer_props.target_object.active_shape_key_index
            if active_key_index >= 0:
                active_key = vertex_transfer_props.target_object.data.shape_keys.key_blocks[active_key_index]
                sk_box.label(text=f"Active: {active_key.name}", icon='RADIOBUT_ON')
            else:
                sk_box.label(text="No active shapekey", icon='RADIOBUT_OFF')
        
        box = layout.box()
        box.label(text="Information", icon='INFO')
        box.label(text="Transfers vertex positions based")
        box.label(text="on vertex indices.")
        box.label(text="Includes active shapekeys in calculation")

class VertexTransferProperties(bpy.types.PropertyGroup):
    source_object: PointerProperty(
        name="Source Object",
        description="Object to transfer vertex positions from",
        type=bpy.types.Object,
        poll=lambda self, obj: obj and obj.type == 'MESH'
    )
    
    target_object: PointerProperty(
        name="Target Object",
        description="Object to transfer vertex positions to",
        type=bpy.types.Object,
        poll=lambda self, obj: obj and obj.type == 'MESH'
    )
    
    blend_factor: FloatProperty(
        name="Blend Factor",
        description="Blend factor between original and transferred positions",
        default=1.0,
        min=0.0,
        max=1.0,
    )
    
    transfer_to_active_shapekey: BoolProperty(
        name="Transfer to Active Shapekey",
        description="Transfer to active shapekey if target has shapekeys",
        default=True,
    )
    
    only_selected_vertices: BoolProperty(
        name="Only Selected Vertices",
        description="Only transfer positions for selected vertices",
        default=False,
    )

class MESH_OT_create_transfer_shapekey(Operator):
    """Create a new shapekey on target if needed"""
    bl_idname = "mesh.create_transfer_shapekey"
    bl_label = "Create Transfer ShapeKey"
    bl_options = {'REGISTER', 'UNDO'}
    
    shapekey_name: bpy.props.StringProperty(
        name="ShapeKey Name",
        description="Name for the new shapekey",
        default="TransferKey"
    )
    
    def execute(self, context):
        scene = context.scene
        vertex_transfer_props = scene.vertex_transfer_props
        target_obj = vertex_transfer_props.target_object
        
        if not target_obj:
            self.report({'ERROR'}, "Target object must be selected!")
            return {'CANCELLED'}
        
        if target_obj.type != 'MESH':
            self.report({'ERROR'}, "Target must be a mesh object!")
            return {'CANCELLED'}
        
        original_active = context.view_layer.objects.active
        original_mode = context.mode
        
        context.view_layer.objects.active = target_obj
        
        if original_mode == 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='OBJECT')
        
        try:
            if not target_obj.data.shape_keys:
                basis = target_obj.shape_key_add(name='Basis')
            
            new_key = target_obj.shape_key_add(name=self.shapekey_name)
            target_obj.active_shape_key_index = len(target_obj.data.shape_keys.key_blocks) - 1
            
            self.report({'INFO'}, f"Created new shapekey: {self.shapekey_name}")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Error: {str(e)}")
            return {'CANCELLED'}
            
        finally:
            context.view_layer.objects.active = original_active
            if original_mode == 'EDIT_MESH':
                bpy.ops.object.mode_set(mode='EDIT')

classes = (
    MESH_OT_transfer_vertex_positions,
    MESH_OT_check_vertex_counts,
    MESH_OT_create_transfer_shapekey,
    MESH_PT_vertex_transfer,
    VertexTransferProperties,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.vertex_transfer_props = PointerProperty(type=VertexTransferProperties)
    
    # UI'yi zorla güncelle
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            area.tag_redraw()
    
    print("Vertex Position Transfer addon registered successfully!")

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.vertex_transfer_props
    print("Vertex Position Transfer addon unregistered.")

if __name__ == "__main__":
    register()
