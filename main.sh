rm -r /data/symmetry/data/shapenet-r2n2/0*
find /data/archive/ShapeNetCore.v1 -name 'model.obj' -print0 | xargs -0 -n1 -P12 -I {} nice -n 12 blender-2.79b-linux-glibc219-x86_64/blender template.blend --background --python render_r2n2.py -- --output_folder /data/symmetry/data/shapenet-r2n2 {}
