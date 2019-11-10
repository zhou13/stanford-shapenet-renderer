rm -rf /data/symmetry/data/shapenet-r2n2
mkdir /data/symmetry/data/shapenet-r2n2
find /data/archive/ShapeNetCore.v2 -name 'model.obj' -print0 | xargs -0 -n1 -P12 -I {} nice -n 12 blender-2.79b-linux-glibc219-x86_64/blender template.blend --background --python render_blender2.py -- --output_folder /data/symmetry/data/shapenet-r2n2 {}
