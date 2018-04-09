using_midi = True
duration = 60 #seconds

family_identities = [0,1] #alternates back and forth between 2 families
slot_system = [0,2,2,0,2,2] #single note,5th,5th,single note,5th,5th, = 1 full family
family_size = len(slot_system)
family_count = len(family_identities)

family_notes = []
for i in range(len(set(family_identities))):
    family_notes.append([])

midi_note_hybrid_current_slot = -1
midi_note_hybrid_current_family = 0

path_type, path_phase = [""]*20,[""]*20

all_cx, all_cy = [[0]],[[0]]

frame_height, frame_width = 0,0