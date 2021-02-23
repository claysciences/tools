import json
import os
import re
import sys
from collections import OrderedDict, defaultdict


class ResultsExplorer:
  # store annotations for a specific media file/frame, so can compare to new annotations later
  prev = {
    'labeled_data': None,
    'frame_num': None,
    'objects': {},
    'seen_frames': 0
  }

  def __init__(self, fname):
    self.fname = fname

  def load_annotations(self):
    print("-- opening '{}' --".format(self.fname), file=sys.stderr)
    with open(self.fname) as ff:
      self.annotations = json.load(ff)
      return self.annotations


  def flush_last_frame(self):
    if len(self.prev["objects"]) > 0:
        for object_id, obj in self.prev["objects"].items():
          self.trigger_ending_obj(self.prev["labeled_data"], self.prev["frame_num"], object_id, obj)

    self.trigger_end_media(self.prev["labeled_data"], self.prev["frame_num"])
    return

  def copy_data(self, labeled_data, frame_num, objs):
    if self.prev["labeled_data"] == labeled_data:
      self.prev["seen_frames"] += 1
    else:
      self.prev["labeled_data"] = labeled_data
      self.prev["seen_frames"] = 1
    
    self.prev["frame_num"] = frame_num
    self.prev["objects"] = objs

  def trigger_start_media(self, labeled_data, frame_num):
    print("-- processing annotations for media file {} --".format(labeled_data), file=sys.stderr)

    print("")
    print("Starting new media: {} starts at frame {}".format(labeled_data, frame_num))

  def trigger_end_media(self, labeled_data, frame_num):
    print("Media ended: {} last annotated frame was {}\n".format(labeled_data, frame_num))

  def trigger_starting_obj(self, labeled_data, frame_num, object_id, obj):
    print("[-->  Object {} ('{}') appears at frame {}".format(object_id, obj["class"], frame_num))

  def trigger_ending_obj(self, labeled_data, frame_num, object_id, obj):
    print(" <--] Object {} ('{}') disappears at frame {}".format(object_id, obj["class"], frame_num))

  def trigger_explicit_obj(self, labeled_data, frame_num, object_id, obj):
    print(" * Object {} ('{}') is explicitly modified at frame {}: {}".format(object_id, obj["class"], frame_num, self.get_object_attributes(obj)))

  def get_object_attributes(self, obj):
    flags = []
    fixed_attributes = ["explicit", "explicit_attributes", "implicit", "implicit_attributes"]
    for att in fixed_attributes:
      if obj["attributes"][att]:
        flags.append("Y") 
      else:
        flags.append("-")

    attributes = []
    skipset = set(fixed_attributes)
    other = set(obj["attributes"].keys()) - skipset
    for att in other:
      attributes.append(obj["attributes"][att])
    return "".join(flags) + " " + ", ".join(attributes)


  def compare_new_frame(self, labeled_data, frame_num, objs):
    # 1) first handle the case of cold-start
    #  trigger new media file
    #  mark all objects in frame as newly appearing
    #  mark all objects in frame as explicitly changed

    if self.prev["labeled_data"] is None:
      self.copy_data(labeled_data, frame_num, objs)
      self.trigger_start_media(labeled_data, frame_num)

      for object_id, obj in objs.items():
        self.trigger_starting_obj(labeled_data, frame_num, object_id, obj)
      
      for object_id, obj in objs.items():
        assert(is_explicit(obj))
        self.trigger_explicit_obj(labeled_data, frame_num, object_id, obj)

      return

    # 2) handle the case of starting a new media/video file
    #  mark all objects in last frame of old file as disappearing
    #  trigger ending media file for old file
    #  
    #  trigger new media file
    #  mark all objects in frame as newly appearing
    #  mark all objects in frame as explicitly changed
    if labeled_data != self.prev["labeled_data"]:
      if len(self.prev["objects"]) > 0:
        for object_id, obj in self.prev["objects"].items():
          self.trigger_ending_obj(self.prev["labeled_data"], self.prev["frame_num"], object_id, obj)
      self.trigger_end_media(self.prev["labeled_data"], self.prev["frame_num"])

      # done with sending previous media/video events.

      self.copy_data(labeled_data, frame_num, objs) 

      # report new video/frame data
      self.trigger_start_media(labeled_data, frame_num)
      for object_id, obj in objs.items():
        self.trigger_starting_obj(labeled_data, frame_num, object_id, obj)
        
      for object_id, obj in objs.items():
        assert(is_explicit(obj))
        self.trigger_explicit_obj(labeled_data, frame_num, object_id, obj)
        
      return
  
    # 3) handle the case of continuing annotations on same media/video file
    #  mark all objects that have explicitly changed in frame as explicitly changed
    #  mark all objects which appeared in prev frame and not in new frame as disappearing in prev frame
    #  mark all objects which are new to this frame as newly appearing
    if labeled_data == self.prev["labeled_data"]:
      for object_id, obj in objs.items():
        if is_explicit(obj):
          self.trigger_explicit_obj(labeled_data, frame_num, object_id, obj)

      prev_objs = set(self.prev["objects"].keys())
      current_objs = set(objs.keys())

      newly_disappearing = prev_objs - current_objs
      if len(newly_disappearing) > 0:
        for o_id in newly_disappearing:
          self.trigger_ending_obj(labeled_data, self.prev["frame_num"], o_id, self.prev["objects"][o_id])

      newly_appearing = current_objs - prev_objs
      if len(newly_appearing) > 0:
        for o_id in newly_appearing:
          self.trigger_starting_obj(labeled_data, frame_num, o_id, objs[o_id])

      # done with comparing prev/this frame, save data for future
      self.copy_data(labeled_data, frame_num, objs) 
      return

    print("--- There's likely an error, this line should not be reached ---", file=sys.stderr)
    

  def extract_annotation_events(self, anns):
    """
    counts number of objects that appear in each frame, and builds a mapping from id to class/type.
    """
    labeled_data = OrderedDict()

    for frame in anns:
      long_data = frame["Labeled Data"]
      short_data = long_data.split("/")[-1]
      if long_data not in labeled_data:
        labeled_data[long_data] = short_data

      frame_num = int(frame["Frame"])
      frame_data = frame["Label"]

      self.compare_new_frame(long_data, frame_num, frame_data)

    self.flush_last_frame()
    print("-- done --", file=sys.stderr)
    return labeled_data

def is_explicit(obj):
  return obj["attributes"]["explicit"] or obj["attributes"]["explicit_attributes"]

    

if __name__ == "__main__":
  cnt  = 0
  if len(sys.argv) == 2:
    results_file = sys.argv[1]

    explorer = ResultsExplorer(results_file)
    anns = explorer.load_annotations()
    labeled_data = explorer.extract_annotation_events(anns)

  else:
      print("Usage: %s <annotations.json>" % sys.argv[0], file=sys.stderr)
