# A simple script that uses blender to render views of a single object by rotation the camera around it.
# Also produces depth map at the same time.
#
# Example:
#   blender template.blend --background --python render_blender.py -- --output_folder /tmp /data/shapenet/ShapeNetCore.v2/02958343/1a0bc9ab92c915167ae33d942430658c/models/model_normalized.obj
#

import os
import sys
import json
import random
import argparse
from math import radians
from random import uniform

import numpy as np

import bpy

# fmt: off
parser = argparse.ArgumentParser(description='Renders given obj file by rotation a camera around it.')
parser.add_argument('obj', type=str,
                    help='Path to the obj file to be rendered.')
parser.add_argument('--output_folder', type=str, default='/tmp',
                    help='The path the output will be dumped to.')
parser.add_argument('--dump', action='store_true',
                    help='Save the blend file')
parser.add_argument('--scale', type=float, default=1,
                    help='Scaling factor applied to model. Depends on size of mesh.')
parser.add_argument('--remove_doubles', type=bool, default=True,
                    help='Remove double vertices to improve mesh quality.')
parser.add_argument('--edge_split', type=bool, default=True,
                    help='Adds edge split filter.')

argv = sys.argv[sys.argv.index("--") + 1:]
args = parser.parse_args(argv)
# fmt: on


def tolist2d(xs):
    return [list(x) for x in xs]


def camera_matrix(camera, render):
    modelview_matrix = camera.matrix_world.inverted()
    projection_matrix = camera.calc_matrix_camera(
        render.resolution_x,
        render.resolution_y,
        render.pixel_aspect_x,
        render.pixel_aspect_y,
    )
    return modelview_matrix, projection_matrix


# Set up rendering of depth map.
bpy.context.scene.use_nodes = True
bpy.context.scene.render.threads_mode = "FIXED"
bpy.context.scene.render.threads = 4
tree = bpy.context.scene.node_tree
links = tree.links

# Add passes for additionally dumping albedo and normals.
bpy.context.scene.render.layers["RenderLayer"].use_pass_normal = True
bpy.context.scene.render.layers["RenderLayer"].use_pass_color = True
bpy.context.scene.render.image_settings.file_format = "OPEN_EXR"
bpy.context.scene.render.image_settings.color_depth = "16"

# Clear default nodes
for n in tree.nodes:
    tree.nodes.remove(n)

# Create input render layer node.
render_layers = tree.nodes.new("CompositorNodeRLayers")

depth_file_output = tree.nodes.new(type="CompositorNodeOutputFile")
depth_file_output.label = "Depth Output"
depth_file_output.name = "Depth Output"
links.new(render_layers.outputs["Depth"], depth_file_output.inputs[0])
depth_file_output.format.color_depth = "32"

# Delete default cube
bpy.data.objects["Cube"].select = True
bpy.ops.object.delete()

model_identifier = os.path.split(args.obj)[0].split("/")[-3:-1]
ext_params = np.loadtxt(args.obj.replace("model.obj", "renderings"))
fp = os.path.join(args.output_folder, *model_identifier) + "/"
bpy.ops.import_scene.obj(filepath=args.obj)
for object in bpy.context.scene.objects:
    if object.name in ["Camera", "Lamp"]:
        continue
    bpy.context.scene.objects.active = object
    if args.scale != 1:
        bpy.ops.transform.resize(value=(args.scale, args.scale, args.scale))
        bpy.ops.object.transform_apply(scale=True)
    if args.remove_doubles:
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.remove_doubles()
        bpy.ops.object.mode_set(mode="OBJECT")
    if args.edge_split:
        bpy.ops.object.modifier_add(type="EDGE_SPLIT")
        bpy.context.object.modifiers["EdgeSplit"].split_angle = 1.32645
        bpy.ops.object.modifier_apply(apply_as="DATA", modifier="EdgeSplit")

# Make light just directional, disable shadows.
lamp = bpy.data.lamps["Lamp"]
lamp.type = "SUN"
lamp.shadow_method = "NOSHADOW"
# Possibly disable specular shading:
lamp.use_specular = False

# Add another light source so stuff facing away from light is not completely dark
bpy.ops.object.lamp_add(type="SUN")
lamp2 = bpy.data.lamps["Sun"]
lamp2.shadow_method = "NOSHADOW"
lamp2.use_specular = False
lamp2.energy = 0.015
bpy.data.objects["Sun"].rotation_euler = bpy.data.objects["Lamp"].rotation_euler
bpy.data.objects["Sun"].rotation_euler[0] += 180


def parent_obj_to_camera(b_camera):
    origin = (0, 0, 0)
    b_empty = bpy.data.objects.new("Empty", None)
    b_empty.location = origin
    b_camera.parent = b_empty  # setup parenting

    scn = bpy.context.scene
    scn.objects.link(b_empty)
    scn.objects.active = b_empty
    return b_empty


scene = bpy.context.scene
scene.render.resolution_x = 256
scene.render.resolution_y = 256
scene.render.resolution_percentage = 100
scene.render.alpha_mode = "TRANSPARENT"
cam = scene.objects["Camera"]
cam.location = (0, 0, 1.5)
cam_constraint = cam.constraints.new(type="TRACK_TO")
cam_constraint.track_axis = "TRACK_NEGATIVE_Z"
cam_constraint.up_axis = "UP_Y"
b_empty = parent_obj_to_camera(cam)
cam_constraint.target = b_empty

scene.render.image_settings.file_format = "PNG"  # set output format to .png
scene.render.image_settings.color_depth = "8"

stepsize_pitch = -radians(90 / (args.views_pitch + 1))
rotation_mode = "XYZ"

if args.dump:
    bpy.ops.wm.save_as_mainfile(filepath="dump.blend")

depth_file_output.base_path = ""
# normal_file_output.base_path = ""
# albedo_file_output.base_path = ""

for i, (azimuth, elevation, _, distance, _) in enumerate(ext_params):
    b_empty.rotation_euler = [radians(elevation), 0, radians(azimuth)]
    cam.location = (0, 0, distance)
    bpy.context.scene.update()  # update camera information for json

    prefix = "{}{:02d}".format(fp, i)
    scene.render.filepath = prefix
    depth_file_output.file_slots[0].path = scene.render.filepath + "_depth"

    # render
    if not os.path.exists("{}.png".format(prefix)):
        bpy.ops.render.render(write_still=True)

    # save camera
    RT, K = camera_matrix(cam, scene.render)
    with open("{}.json".format(prefix), "w") as f:
        json.dump({"RT": tolist2d(RT), "K": tolist2d(K)}, f)
