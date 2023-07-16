import json
import sys
from pathlib import Path

import cv2
import pandas as pd

EMPTY_ANNOTATION = [""]

def get_video_length(url):
    length = -1
    if url is None:
        return -1
    
    try:
        cap = cv2.VideoCapture(url)
        cv2length = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if cv2length > 0:
            length = cv2length
            
    except cv2.error as e:
        print(f"Failed to get frame count from '{url}'", file=sys.stderr)

    finally:
        return length
    
def extract_from_json(json_filename):
    attributes = []
    framenums = []
    labeled_data_video = None

    if not Path(json_filename).exists():
        print(f"File {json_filename} does not exist", file=sys.stderr)
        return attributes, framenums, labeled_data_video
    
    with open(json_filename, "r") as f:
        jj = json.load(f)
        for frame in jj:
            labeled_data_video = frame["Labeled Data"]
            att = frame["Label"]["0"]["attributes"]
            # if att == EMPTY_ANNOTATION:
            #     att = None
            framenum = int(frame["Frame"])
            attributes.append(att)
            framenums.append(framenum)

    return attributes, framenums, labeled_data_video


def main(json_file):
    attributes, framenums, labeled_data_video = extract_from_json(json_file)
    total_frames = get_video_length(labeled_data_video)
    print(f"Video '{labeled_data_video}' has {total_frames} frames")

    if len(framenums) == 0:
        print(f"No annotaitons found in file '{json_file}'")
        sys.exit(0)


    # if first annotation starts at frame > 0, add an empty annotation for frame 0
    if framenums[0] > 0:
        # if first annoation is empty, but starts at frame > 0, just move it to frame 0
        if attributes[0] == EMPTY_ANNOTATION:
            framenums[0] = 0
        else: 
            # prefix with empty annotation at frame 0 
            framenums = [0] + framenums
            attributes = [EMPTY_ANNOTATION] + attributes

    # get end_frames
    end_frame_nums = [x-1 for x in framenums[1:]] + [total_frames]


    for start_frame, end_frame, att in zip(framenums, end_frame_nums, attributes):
        if att == EMPTY_ANNOTATION:
            print(f'Frames {start_frame:4} - {end_frame:4} have no attributes')
        else:
            print(f'Frames {start_frame:4} - {end_frame:4} have attributes {att}')
        
if __name__ == "__main__":
    if len(sys.argv) != 2:       
        print("This will read a Clay Sciences scene annotation json dump and parse it") 
        print(f"Usage: {Path(sys.argv[0]).name} <json_file>")
        sys.exit(-1)

    main(sys.argv[1])
