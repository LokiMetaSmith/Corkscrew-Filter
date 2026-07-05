# blender_viz.py - Script for Blender/bpy
import bpy
import sys
import os

def setup_blender_scene(x3d_file):
    # Clear existing objects
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    # Import X3D
    print(f"Importing X3D: {x3d_file}")
    bpy.ops.import_scene.x3d(filepath=x3d_file)

    # Find the imported mesh
    imported_objs = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']

    if not imported_objs:
        print("No mesh found in X3D file.")
        return

    main_obj = imported_objs[0]
    main_obj.name = "EM_Simulation_Data"

    # Setup Geometry Nodes
    print("Setting up Geometry Nodes...")
    gn_modifier = main_obj.modifiers.new(name="VizNodes", type='NODES')
    node_group = bpy.data.node_groups.new(name="EM_Viz", type='GeometryNodeTree')
    gn_modifier.node_group = node_group

    nodes = node_group.nodes
    links = node_group.links

    # Basic setup: Input -> Group Output
    node_in = nodes.new(type='NodeGroupInput')
    node_out = nodes.new(type='NodeGroupOutput')

    # Handle interface for both Blender 4.0+ and 3.x
    if hasattr(node_group, "interface"):
        node_group.interface.new_socket(name="Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
        node_group.interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    else:
        node_group.inputs.new('NodeSocketGeometry', 'Geometry')
        node_group.outputs.new('NodeSocketGeometry', 'Geometry')

    # Animation and Transformation nodes
    node_time = nodes.new(type='GeometryNodeInputSceneTime')
    node_math = nodes.new(type='ShaderNodeMath')
    node_math.operation = 'SINE'

    node_combine = nodes.new(type='ShaderNodeCombineXYZ')
    node_transform = nodes.new(type='GeometryNodeTransform')
    node_mat = nodes.new(type='GeometryNodeSetMaterial')

    # Link nodes
    links.new(node_in.outputs[0], node_transform.inputs[0])
    links.new(node_transform.outputs[0], node_mat.inputs[0])
    links.new(node_mat.outputs[0], node_out.inputs[0])

    # Simple z-oscillation animation
    # inputs[1] of Transform is Translation
    links.new(node_time.outputs[1], node_math.inputs[0]) # Seconds to Sine
    links.new(node_math.outputs[0], node_combine.inputs[2]) # Sine to Z-channel
    links.new(node_combine.outputs[0], node_transform.inputs[1]) # Combined XYZ to Translation

    # Save the blend file
    output_blend = x3d_file.replace(".x3d", ".blend")
    bpy.ops.wm.save_as_mainfile(filepath=output_blend)
    print(f"Blender scene saved to: {output_blend}")

if __name__ == "__main__":
    if "--" in sys.argv:
        args = sys.argv[sys.argv.index("--") + 1:]
        if args:
            setup_blender_scene(args[0])
        else:
            print("No X3D file provided.")
    else:
        print("Usage: blender --background --python blender_viz.py -- <input_x3d>")
