This add-on is primarily designed to transfer vertex positions between two models with identical vertex counts, based on their vertex indices. It is particularly useful for character models.

For example, if you have multiple facial expressions of the same character, you might not always be able to transfer these as shape keys in Blender. This is because shape keys require the "basis" of both models to be exactly the same. If you've created these facial expressions in a different program and are keeping them as separate models in Blender, this add-on can help you merge them as either default shapes or shape keys.
How to Use:

Selecting Models:

  Choose the correct Source and Target models.

  The source model can have multiple shape keys, which should be active for the transfer.

  If the target model does not have any shape keys, the vertex positions will be directly transferred.

  If the target model has an active shape key, the vertex position data will be applied directly to that shape key.

Adjusting Transfer Intensity:

  After transferring the vertex data, you can adjust the transfer strength from the popup window in the lower left corner, choosing the percentage of influence you want.

Accessing the Add-on:

You can access the add-on from the Tool menu in the right-side panel.

Feel free to use and develop this add-on as you like. 😊
