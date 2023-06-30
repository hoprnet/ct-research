import imageio
import glob
import os

def convert_images_to_video(images, output_file, format='GIF', duration=0.5):
    frames = []
    for filename in images:
        frames.append(imageio.imread(filename))
    imageio.mimsave(output_file, frames, format=format, duration=duration)
    

image_dir = '.'  # directory where the images are stored
pattern = 'net_viz-*.png'  # pattern to match the image files

# Find all PNG files in the directory that match the pattern
file_list = glob.glob(os.path.join(image_dir, pattern))

# Sort the file list by name (in ascending order)
file_list.sort()
    
output_file = 'output.gif'
convert_images_to_video(file_list, output_file, format='GIF', duration=0.5)

