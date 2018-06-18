from music_helper import get_notes_in_scale
import time #for sending midi
import rtmidi #for sending midi
import threading as th
from settings import *
import settings
from pychord import Chord
import math
import numpy as np #for webcam
import random
import platform
import cv2
play_peak_notes = True
using_height_as_magnitude = True
using_midi = True
midiout = rtmidi.MidiOut()
midi_associations = {}
use_adjust_song_magnitude = False
use_override_notes,override_notes = False,[]
soundscape_image = cv2.imread('soundscape.png',1)

def position_to_midi_value(current_position, max_position, edge_buffer):
    value = 0
    if current_position<edge_buffer:
        value = 127
    elif current_position>max_position-edge_buffer:
        value = 0
    else:
        value = int(127*((current_position-edge_buffer)/(max_position-edge_buffer*2)))
    return value
rotating_sound_num = 0

def rotational_selecter(ball_index, list_of_notes):
    global rotating_sound_num
    skip_random_note = True    
    rotating_sound_num = rotating_sound_num + 1
    if skip_random_note:
        if random.randint(0,100) < 20:
            rotating_sound_num = rotating_sound_num + 1
    if rotating_sound_num >= len(list_of_notes):
        rotating_sound_num = 0
    return list_of_notes[rotating_sound_num]

def positional_selecter(ball_index, list_of_notes):
    positional_selecter_is_in_use = True
    rounded_to_list = True
    max_position = settings.frame_width
    notes_to_return = []
    stretched_note_positions = []
    section_size = max_position/len(list_of_notes)
    for i in range(len(list_of_notes)):
        stretched_note_positions.append(int(i*section_size+section_size*.5))
    triggered_section_position = min(stretched_note_positions, key=lambda x:abs(x-all_cx[ball_index][-1]))
    triggered_section_index = stretched_note_positions.index(triggered_section_position)
    '''midi_associations['ball '+str(ball_index)]['peak']['mid column']['times_position_triggered'][triggered_section_index]+=1
    for i in range(4):
        if i != triggered_section_index:
            midi_associations['ball '+str(ball_index)]['peak']['mid column']['times_position_triggered'][triggered_section_index]=0'''
    if settings.play_chords_as_arpeggio:
        #cur_arpeggio_index = midi_associations['ball '+str(ball_index)]['peak']['mid column']['times_position_triggered'][triggered_section_index]%len(settings.scale_to_use[triggered_section_index])
        notes_to_return = list_of_notes[triggered_section_index][cur_arpeggio_index]
    else:
        notes_to_return = list_of_notes[triggered_section_index]
    return notes_to_return

def honeycomb_selecter(index, list_of_notes):
    notes_to_return = []
    honeycomb_diameter = settings.frame_width/settings.number_of_honeycomb_rows
    number_of_honeycomb_columns = settings.frame_height/honeycomb_diameter+1
    total_number_of_honeycombs = number_of_honeycomb_rows * number_of_honeycomb_columns
    ball_x = all_cx[index][-1]
    ball_y = all_cy[index][-1]
    closest_x_index,closest_y_index = 0.0,0.0
    if math.floor((ball_y/honeycomb_diameter+.5)%2)==0:
        closest_x_index = round(ball_x / honeycomb_diameter)
        closest_y_index = round(ball_y / honeycomb_diameter)       
    else:
        closest_x_index = round((ball_x / honeycomb_diameter-.5)+.5)
        closest_y_index = round(ball_y / honeycomb_diameter)
    index_to_use = closest_x_index*closest_y_index
    if index_to_use != 0:
        index_to_use = index_to_use%len(list_of_notes)
    if len(list_of_notes) > 0:
        return list_of_notes[index_to_use]
    else:
        return 0

def hybrid_selecter(index, list_of_notes):
    global use_override_notes,override_notes
    settings.midi_note_hybrid_current_slot = settings.midi_note_hybrid_current_slot + 1
    if settings.midi_note_hybrid_current_slot == settings.family_size:
        settings.midi_note_hybrid_current_slot = 0
        settings.midi_note_hybrid_current_family = settings.midi_note_hybrid_current_family + 1
        if settings.midi_note_hybrid_current_family == settings.family_count:
            settings.midi_note_hybrid_current_family = 0
    this_families_identity = settings.family_identities[settings.midi_note_hybrid_current_family]
    should_retrieve_notes = False
    if settings.family_notes[this_families_identity]:
        notes_retrieved = settings.family_notes[this_families_identity]
    else:
        should_retrieve_notes = True
    if should_retrieve_notes == True:
        notes_retrieved = positional_selecter(index, list_of_notes)
        settings.family_notes[this_families_identity] = notes_retrieved
        settings.midi_note_hybrid_current_slot = 0
    if use_override_notes:
        use_override_notes = False
        notes_retrieved = override_notes
        settings.family_notes[this_families_identity] = notes_retrieved
        settings.midi_note_hybrid_current_slot = 0
    number_of_notes_to_use = settings.slot_system[settings.midi_note_hybrid_current_slot]
    notes_to_return = notes_retrieved[0:number_of_notes_to_use+1]
    return notes_to_return

def midi_magnitude(index):
    return 112

def midi_modulator(index, type, channel, controller_num):
    value = 0
    if type == 'width':
        value = position_to_midi_value(all_cx[index][-1],settings.frame_width,0)
    if type == 'height':
        value = position_to_midi_value(all_cy[index][-1],480,0)
    return [channel, controller_num, value]

def get_midi_from_letter(letter, current_octave):
    sharp_letters = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
    flat_letters = ['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B']
    if 'b' in letter:
        return flat_letters.index(letter)+(current_octave - 4 )*12 + 60
    else:
        return sharp_letters.index(letter)+(current_octave - 4 )*12 + 60
loop_creator_counter = 0

def loop_creator(note):
    print('p')
    global loop_creator_counter
    if loop_creator_counter == 0:
        send_midi_note_on_only(2,note,100)
    if loop_creator_counter == 1:
        send_midi_note_on_only(2,note,100)
        settings.in_melody = True
        create_association_object()
    loop_creator_counter =+ 1
    return note 

def setup_midi():    
    available_ports = midiout.get_ports()
    if available_ports:
        try:
            if platform.system().lower() == "darwin":
                port_num = 0
            else:
                port_num = 1
            midiout.open_port(port_num)
        except:
            pass
    else:
        midiout.open_virtual_port('My virtual output')

def get_midi_note(ball_index,path_phase,path_type):
    channel = 0
    notes = []
    magnitude = 0
    this_path_phase = path_phase[ball_index]
    this_path_type = path_type[ball_index]
    is_ongoing = False
    if this_path_phase in midi_associations['ball '+str(ball_index)]:
        if this_path_type in midi_associations['ball '+str(ball_index)][this_path_phase]:
            if 'channel' in midi_associations['ball '+str(ball_index)][this_path_phase][this_path_type]:
                channel = midi_associations['ball '+str(ball_index)][this_path_phase][this_path_type]['channel']           
            if 'notes' in midi_associations['ball '+str(ball_index)][this_path_phase][this_path_type]:
                all_possible_notes = midi_associations['ball '+str(ball_index)][this_path_phase][this_path_type]['notes']
                if midi_associations['ball '+str(ball_index)][this_path_phase][this_path_type]['note_selection_mode'] == 'rotational':
                        notes = rotational_selecter(ball_index,all_possible_notes)
                if midi_associations['ball '+str(ball_index)][this_path_phase][this_path_type]['note_selection_mode'] == 'current positional':
                        print('current positional')
                        notes = positional_selecter(ball_index,all_possible_notes)
                if midi_associations['ball '+str(ball_index)][this_path_phase][this_path_type]['note_selection_mode'] == 'hybrid':
                        notes = hybrid_selecter(ball_index,all_possible_notes)
                if midi_associations['ball '+str(ball_index)][this_path_phase][this_path_type]['note_selection_mode'] == 'loop':
                        notes = loop_creator(all_possible_notes)
            if 'magnitude' in midi_associations['ball '+str(ball_index)][this_path_phase][this_path_type]:
                magnitude = midi_associations['ball '+str(ball_index)][this_path_phase][this_path_type]['magnitude'](ball_index)    
    if 'all phases' in midi_associations['ball '+str(ball_index)]:
        if midi_associations['ball '+str(ball_index)]['all phases']['all types']['note_selection_mode'] == 'honeycomb':
            is_ongoing = True
            all_possible_notes = midi_associations['ball '+str(ball_index)]['all phases']['all types']['notes']
            notes = honeycomb_selecter(ball_index,all_possible_notes)
            magnitude = midi_associations['ball '+str(ball_index)]['all phases']['all types']['magnitude'](ball_index)
            channel = midi_associations['ball '+str(ball_index)]['all phases']['all types']['channel']
    return channel, notes, magnitude, is_ongoing

def get_midi_modulation(ball_index,path_phase,path_type):
    this_path_phase = path_phase[ball_index]
    this_path_type = path_type[ball_index]
    modulators = []
    if this_path_phase in midi_associations['ball '+str(ball_index)]:
        if this_path_type in midi_associations['ball '+str(ball_index)][this_path_phase]:
            if 'modulator' in midi_associations['ball '+str(ball_index)][this_path_phase][this_path_type]:
                for i in midi_associations['ball '+str(ball_index)][this_path_phase][this_path_type]['modulator']:
                    modulators.append(midi_modulator(ball_index, i[0], i[1], i[2]))
    return modulators

def send_midi_messages(channel, notes, magnitude, modulators): 
    for i in modulators:
        send_midi_cc(i[0],i[1],i[2])
    try:
        send_midi_note(channel,notes,magnitude)
    except TypeError:
        for n in notes:
            send_midi_note(channel,n,magnitude)

def get_wav_sample(index):
    note = 1
    return note, magnitude

def get_wav_modulation(index):
    modulation = 1
    return modulation

def send_wav_messages(note, magnitude, modulation):
    nothing = 0

def midi_note_channel_num(channel,on_or_off):
    if on_or_off == 'on':
        i = int('0x90', 16)
    elif on_or_off == 'off':     
        i = int('0x80', 16)     
    i += int(channel)
    return i

def midi_cc_channel_num(channel):
    i = int('0xB0', 16)
    i += int(channel)
    return i
midi_channel_to_off = 0
midi_note_to_off = 0

def send_midi_note_on_only(channel,note,magnitude):
    note_on = [midi_note_channel_num(channel,'on'), note, magnitude]
    midiout.send_message(note_on)

def turn_midi_note_off(channel,note):
    note_off = [midi_note_channel_num(channel,'off'), note, 0]
    try:
        midiout.send_message(note_off)
    except:
        pass

def send_midi_note(channel,note,magnitude):                  
    note_on = [midi_note_channel_num(channel,'on'), note, magnitude]
    #print(note_on)
    midiout.send_message(note_on)
    midi_channel_to_off = channel
    midi_note_to_off = note
    off = th.Timer(0.4,turn_midi_note_off, args = [channel,note])     
    off.start()

def use_as_midi_signal(current_num,max_num):
    return 127*(current_num/max_num)

def send_midi_cc(channel,controller_num,value):
    send_cc = [midi_cc_channel_num(channel), controller_num, value]
    midiout.send_message(send_cc)

def adjust_song_magnitude(axis,edge_buffer,position,song):
    if axis == 'y':
        size = settings.frame_height        
    if axis == 'x':
        size = settings.frame_width
    if position<edge_buffer:
        song.set_magnitude(1)
    if position>frame_height-edge_buffer:
        song.set_magnitude(0)
    song.set_magnitude((position-edge_buffer)/(size-edge_buffer*2))

def average_position(all_axis, window_length, window_end_frame):
    average_pos = 0
    count = 0
    average_duration = min(len(all_axis[0]), window_length)
    for i in range(0, len(all_axis)):
        for j in range(0, average_duration):
            index = window_end_frame-j
            if abs(index)<len(all_axis[i]):
                if not all_axis[i][index] == 'X':
                    if all_axis[i][index] > 0:
                        if not all_axis[i][index] == 'X':
                            count = count+1
                            average_pos = average_pos + all_axis[i][index]
    if count > 0:
        average_pos = average_pos/count
    return average_pos
last_note_sent = 0

def average_position_of_multiple_single_ball_average_positions(list_of_single_ball_average_positions):
    number_of_single_ball_average_positions_to_average = len(list_of_single_ball_average_positions)
    sum_of_x_axis = 0
    sum_of_y_axis = 0
    number_of_balls_seen = 0
    average_x_position = 0
    average_y_position = 0
    for i in range (number_of_single_ball_average_positions_to_average):
        if list_of_single_ball_average_positions[i]:
            if len(list_of_single_ball_average_positions[i])>1:
                sum_of_x_axis += list_of_single_ball_average_positions[i][0]
                sum_of_y_axis += list_of_single_ball_average_positions[i][1]
                number_of_balls_seen += 1
    if number_of_balls_seen > 0:
        average_x_position = sum_of_x_axis/number_of_balls_seen
        average_y_position = sum_of_y_axis/number_of_balls_seen
    return([average_x_position,average_y_position])
    #todo it is flickering between the actual average position and 0 constantly down in 'send_midi_cc_based_on_average_position'
    #   and so i figure the issue must be here, or somewhere before here, like below in 'average_position_of_single_ball'

def average_position_of_single_ball(ball_number, window_length):
    ball_number = int(ball_number)
    axes = [all_cx[ball_number], all_cy[ball_number]]
    average_positions = []
    average_duration = min(len(axes)+1, int(window_length)+1)
    for axis in axes:
        count = 0
        average_position_of_current_axis = 0
        for j in range(1, average_duration):
            if abs(j)<len(axis)+1:
                if not axis[-j] == 'X':
                    if axis[-j] > 0:
                        if not axis[-j] == 'X':
                            count = count+1
                            average_position_of_current_axis = average_position_of_current_axis + axis[-j]
        if count > 0:
            average_position_of_current_axis = average_position_of_current_axis/count
            average_positions.append(average_position_of_current_axis)
    return average_positions

def send_midi_note_from_soundscape_color(soundscape_color):
    soundscape_color = np.array(soundscape_color).tolist()
    average_soundscape_color = (soundscape_color[0]+soundscape_color[1]+soundscape_color[2])/4
    send_midi_messages(2,average_soundscape_color,40,[])

def create_individual_ball_audio(ball_index):
    global use_override_notes,override_notes,last_note_sent
    is_ongoing = False
    if use_adjust_song_magnitude:
        adjust_song_magnitude('y',120,average_position(all_cy, 10, -1),song)
    if using_midi:
        if path_phase[ball_index] == 'putt':
            override_notes = positional_selecter(ball_index,settings.scale_to_use)
            use_override_notes = True
        if settings.using_soundscape:
            soundscape_color = soundscape_image[all_cy[ball_index][-1],all_cx[ball_index][-1]]
            send_midi_note_from_soundscape_color(soundscape_color)
        else:
            if path_phase[ball_index] in midi_associations['ball '+str(ball_index)] and path_type[ball_index] in midi_associations['ball '+str(ball_index)][path_phase[ball_index]]:
                #print('path_type[ball_index]')
                #print(path_type[ball_index])#TODO EACH BALL IS BEING GIVEN A PATH_TYPE(RELATIVE POSITION) BASED ON ITS BALL NUMBER
                channel, notes, magnitude, is_ongoing = get_midi_note(ball_index,path_phase,path_type)         
                modulators = get_midi_modulation(ball_index,path_phase,path_type)
                send_midi_messages(channel, notes, magnitude, modulators)                      
    else:
        note, magnitude = get_wav_sample(ball_index)
        modulation = get_wav_modulation(ball_index)
        send_wav_messages(note, magnitude, modulation)

def is_valid_cc_location_input(location_instance_number,location_direction):
    list_of_ball_numbers = ['1','2','3']
    is_valid = False
    if any(i in list_of_ball_numbers for i in cc_location_object['instance number '+str(location_instance_number)]['balls to average']):
        if int(cc_location_object['instance number '+str(location_instance_number)]['window size']) > 0:
            if cc_location_object['instance number '+str(location_instance_number)][location_direction]['channel'].isdigit():
                if cc_location_object['instance number '+str(location_instance_number)][location_direction]['number'].isdigit():
                    is_valid = True
    return is_valid

def create_multiple_ball_audio():
    if using_midi:
        #todo
        #   i think the averaging stuff is working, although i have not tested it with 3 balls yet
        #   modify send_midi_cc_based_on_average_position to be able to take the thing below in the print
        #print(average_position_of_multiple_single_ball_average_positions([average_position_of_single_ball(0,10),average_position_of_single_ball(1,10)]))
        #print(cc_location_object['instance number 0']['balls to average'])
        #loop through each of the 4 cc locations, inside each of them loop through the 2 axis directions
        #   if they have any balls checked and specifics input, then allow them to use the function

        for i in range (4):
            for location_direction in location_directions:
                if is_valid_cc_location_input(i,location_direction):
                    ball_numbers_to_average = cc_location_object['instance number '+str(i)]['balls to average']
                    window_size = cc_location_object['instance number '+str(i)]['window size']
                    channel = cc_location_object['instance number '+str(i)][location_direction]['channel']
                    number = cc_location_object['instance number '+str(i)][location_direction]['number']
                    list_of_ball_average_positions = [[]]
                    for ball_number in ball_numbers_to_average:
                        list_of_ball_average_positions.append(average_position_of_single_ball(ball_number,window_size))
                    if location_direction == 'horizontal':
                        first_edge = cc_location_object['instance number '+str(i)]['location border sides']['left']
                        second_edge = cc_location_object['instance number '+str(i)]['location border sides']['right']
                        send_midi_cc_based_on_average_position(location_direction,first_edge,second_edge,average_position_of_multiple_single_ball_average_positions(list_of_ball_average_positions)[0],channel,number)
                    if location_direction == 'vertical':
                        first_edge = cc_location_object['instance number '+str(i)]['location border sides']['top']
                        second_edge = cc_location_object['instance number '+str(i)]['location border sides']['bottom']
                        send_midi_cc_based_on_average_position(location_direction,first_edge,second_edge,average_position_of_multiple_single_ball_average_positions(list_of_ball_average_positions)[1],channel,number)
                    
        #more todo
        #   make the location inputs only allow numbers in ui
        #   hook up the ui to the specifics above
        #   show a circle where the average is in the imshow
        #   hook up what we have with position to the velocity lists as well
        #       make the ui for this

        #eventual todo
        #   make it so that the savefiledialog creates a folder that holds a bunch of differnt saved files,
        #       one for each different aspect of the ui as well as anything else that should be saved

        #send_midi_cc_based_on_average_position('y',0,average_position(all_cy, 10, -1))
        #send_midi_cc_based_on_average_position('x',0,average_position(all_cx, 10, -1))
        #send_midi_cc_based_on_average_speed_while_held()
        #send_midi_cc_based_on_average_speed() 

def send_midi_cc_based_on_average_speed_while_held():
    for i in range(3):#average all 6 velocities together over a certain amount of time and then get a low
        print(i)#and high number to be the 0, 128 and figure it out from there

    #IDEALLY FOR POSITION
    #-i can use the average location or average velocity of any ball or combination of balls
    #-there are calibration windows that can be opened for each position instance which can have the borders
    #   buffers set, there should be a key that can be pressed that make it so the mouse acts as the
    #   average position for that position instance 

    #IDEALLY FOR SPEED:
    #-i can use the average velocity of any ball or combination of balls
    #-there are calibration windows that can be opened where the extreme fast juggling can be performed
    #       as well as the extreme slow juggling

def send_midi_cc_based_on_average_position(location_direction,first_edge,second_edge,average_position,channel,number):
    value = 0
    first_edge = int(first_edge)
    second_edge = int(second_edge)
    print('average_position')
    print(average_position)
    print('first_edge')
    print(first_edge)
    print('second_edge')
    print(second_edge)
    if location_direction == 'vertical':
        size = settings.frame_height        
    if location_direction == 'horizontal':
        size = settings.frame_width

    if average_position<first_edge:
        value = 128

    elif average_position>second_edge:
        value = 0
    else:        
        distance_between_edges = abs(first_edge-second_edge)
        print('distance_between_edges')
        print(distance_between_edges)
        distance_between_edge_and_average_position = abs(first_edge-average_position)
        print('distance_between_edge_and_average_position')
        print(distance_between_edge_and_average_position)
        value = max(0,(distance_between_edge_and_average_position/distance_between_edges)*128)

    print(channel +','+ number +','+str(value) )

    send_midi_cc(int(channel),int(number),value)

def create_association_object():

    if settings.using_loop:
        if settings.in_melody:
            settings.scale_to_use = get_notes_in_scale('F',[3,4],'Major',1)
        else:
            midi_notes = []
            midi_notes_with_voicing = []
            chords = ['FM9', 'Am7','BbM7','A7']
            voicing = [[1,5,1,3,7,9],[1,5,1,3,7],[1,5,1,3,7,5],[1,5,1,3,7]]
            for i in range(0,len(chords)):
                midi_notes.append([])
                midi_notes_with_voicing.append([])
                c = Chord(chords[i])
                cur_notes = c.components()
                if '9' in chords[i]:
                    current_octave = 4
                else:
                    current_octave = 3
                last_note = 0      
                for n in cur_notes:
                    note = get_midi_from_letter(n,current_octave)
                    if note < last_note:
                        note = note + 12
                    midi_notes[i].append(note)
                    last_note = note
                    last_chord_with_voicing = 0
                for d in voicing[i]:
                    chord_with_voicing = midi_notes[i][int(math.floor(d/2))]
                    if chord_with_voicing < last_chord_with_voicing:
                        chord_with_voicing = chord_with_voicing + 12                   
                    midi_notes_with_voicing[i].append(chord_with_voicing)
                    last_chord_with_voicing = chord_with_voicing
            settings.scale_to_use = midi_notes_with_voicing
    else:
        settings.scale_to_use = get_notes_in_scale('F',[3,4],'Major',1)
    cross_selection_mode = 'positional'
    column_selection_mode = 'positional'
    settings.grid_type_to_show = 'positional'
    settings.scale_to_use = get_notes_in_scale('F',[1,2,3,4],'Major',1)
    #print(settings.scale_to_use)
    #settings.scale_to_use = [60,62,64,66,68,74,70,74,68,66,66,64,64,62,62,60]
    cross_notes_to_use = settings.scale_to_use
    column_notes_to_use = settings.scale_to_use
    ball_config_index_to_use = [0,0,0]

    for i in range(3):

        if selected_configs_of_balls[i] == 'X':
            ball_config_index_to_use = 0
        if selected_configs_of_balls[i] == 'Y':
            ball_config_index_to_use = 1
        if selected_configs_of_balls[i] == 'Z':
            ball_config_index_to_use = 2

        #print(selected_config_midi_channels[ball_config_index_to_use[i]])
        midi_associations['ball '+str(i)] = {}
        for path_phase in path_phases:
            midi_associations['ball '+str(i)][path_phase] = {}
            for path_type in path_types:
                midi_associations['ball '+str(i)][path_phase][path_type] = {}
                ui_path_point_index = path_point_object[selected_configs_of_balls[i]][path_type][path_phase]
                if ui_path_point_index > 0:
                    if point_setups_input_type[ui_path_point_index] == 'midi':
                        notes_to_use = list(map(int,point_setups_single_line_input[ui_path_point_index].split(',')))
                    midi_associations['ball '+str(i)][path_phase][path_type]['channel'] = selected_config_midi_channels[ball_config_index_to_use]
                    midi_associations['ball '+str(i)][path_phase][path_type]['note_selection_mode'] = point_setups_note_selection_type[ui_path_point_index]
                    midi_associations['ball '+str(i)][path_phase][path_type]['times_position_triggered'] = [-1]*len(settings.scale_to_use)
                    midi_associations['ball '+str(i)][path_phase][path_type]['notes'] = notes_to_use
                    midi_associations['ball '+str(i)][path_phase][path_type]['magnitude'] = midi_magnitude
    #print(midi_associations)

    '''#midi_associations['ball '+str(i)]['peak']['mid column']['modulator'] = [['width',0,0], ['height',0,1]]    
        #midi_associations['ball '+str(i)]['peak']['mid column'] = {}
        #midi_associations['ball '+str(i)]['peak']['mid column']['channel'] = selected_config_midi_channels[ball_config_index_to_use[i]]
        #midi_associations['ball '+str(i)]['peak']['mid column']['notes']['scale_type'] = 
        #midi_associations['ball '+str(i)]['peak']['mid column']['notes']['root'] = 
        #midi_associations['ball '+str(i)]['peak']['mid column']['notes'][''] = chord/scale/individual
        ui_point_index_for_left_column_peak = left_column_peak_path_point_configuration_index[ball_config_index_to_use[i]]
        if ui_point_index_for_left_column_peak > 0:
            if point_setups_input_type[ui_point_index_for_left_column_peak] == 'midi':
                notes_to_use = list(map(int,point_setups_single_line_input[ui_point_index_for_left_column_peak].split(',')))
            midi_associations['ball '+str(i)]['peak']['left column'] = {}
            midi_associations['ball '+str(i)]['peak']['left column']['channel'] = selected_config_midi_channels[ball_config_index_to_use[i]]
            midi_associations['ball '+str(i)]['peak']['left column']['note_selection_mode'] = point_setups_note_selection_type[ui_point_index_for_left_column_peak]
            midi_associations['ball '+str(i)]['peak']['left column']['times_position_triggered'] = [-1]*len(settings.scale_to_use)
            midi_associations['ball '+str(i)]['peak']['left column']['notes'] = notes_to_use
            midi_associations['ball '+str(i)]['peak']['left column']['magnitude'] = midi_magnitude
        #midi_associations['ball '+str(i)]['peak']['left column']['modulator'] = [['width',0,0], ['height',0,1]]
        ui_point_index_for_right_column_peak = right_column_peak_path_point_configuration_index[ball_config_index_to_use[i]]
        if ui_point_index_for_right_column_peak > 0:
            if point_setups_input_type[ui_point_index_for_right_column_peak] == 'midi':
                notes_to_use = list(map(int,point_setups_single_line_input[ui_point_index_for_right_column_peak].split(','))) 
            midi_associations['ball '+str(i)]['peak']['right column'] = {}
            midi_associations['ball '+str(i)]['peak']['right column']['channel'] = selected_config_midi_channels[ball_config_index_to_use[i]]
            midi_associations['ball '+str(i)]['peak']['right column']['note_selection_mode'] = point_setups_note_selection_type[ui_point_index_for_right_column_peak]
            midi_associations['ball '+str(i)]['peak']['right column']['times_position_triggered'] = [-1]*len(settings.scale_to_use)
            midi_associations['ball '+str(i)]['peak']['right column']['notes'] = notes_to_use
            midi_associations['ball '+str(i)]['peak']['right column']['magnitude'] = midi_magnitude
        #midi_associations['ball '+str(i)]['peak']['right column']['modulator'] = [['width',0,0], ['height',0,1]] 
        ui_point_index_for_mid_cross_peak = mid_cross_peak_path_point_configuration_index[ball_config_index_to_use[i]]
        if ui_point_index_for_mid_cross_peak > 0:
            if point_setups_input_type[ui_point_index_for_mid_cross_peak] == 'midi':
                notes_to_use = list(map(int,point_setups_single_line_input[ui_point_index_for_mid_cross_peak].split(',')))
            midi_associations['ball '+str(i)]['peak']['mid cross'] = {}
            midi_associations['ball '+str(i)]['peak']['mid cross']['channel'] = selected_config_midi_channels[ball_config_index_to_use[i]]
            midi_associations['ball '+str(i)]['peak']['mid cross']['note_selection_mode'] = point_setups_note_selection_type[ui_point_index_for_mid_cross_peak]
            midi_associations['ball '+str(i)]['peak']['mid cross']['times_position_triggered'] = [-1]*len(settings.scale_to_use)
            midi_associations['ball '+str(i)]['peak']['mid cross']['notes'] = notes_to_use
            midi_associations['ball '+str(i)]['peak']['mid cross']['magnitude'] = midi_magnitude
        #midi_associations['ball '+str(i)]['peak']['mid cross']['modulator'] = [['width',0,0], ['height',0,1]]
        ui_point_index_for_left_cross_peak = left_cross_peak_path_point_configuration_index[ball_config_index_to_use[i]]
        if ui_point_index_for_left_cross_peak > 0:
            if point_setups_input_type[ui_point_index_for_left_cross_peak] == 'midi':
                notes_to_use = list(map(int,point_setups_single_line_input[ui_point_index_for_left_cross_peak].split(',')))    
            midi_associations['ball '+str(i)]['peak']['left cross'] = {}
            midi_associations['ball '+str(i)]['peak']['left cross']['channel'] = selected_config_midi_channels[ball_config_index_to_use[i]]
            midi_associations['ball '+str(i)]['peak']['left cross']['note_selection_mode'] = point_setups_note_selection_type[ui_point_index_for_left_cross_peak]
            midi_associations['ball '+str(i)]['peak']['left cross']['times_position_triggered'] = [-1]*len(settings.scale_to_use)
            midi_associations['ball '+str(i)]['peak']['left cross']['notes'] = notes_to_use
            midi_associations['ball '+str(i)]['peak']['left cross']['magnitude'] = midi_magnitude
        #midi_associations['ball '+str(i)]['peak']['left cross']['modulator'] = [['width',0,0], ['height',0,1]]
        ui_point_index_for_right_cross_peak = right_cross_peak_path_point_configuration_index[ball_config_index_to_use[i]]
        if ui_point_index_for_right_cross_peak > 0:
            if point_setups_input_type[ui_point_index_for_right_cross_peak] == 'midi':
                notes_to_use = list(map(int,point_setups_single_line_input[ui_point_index_for_right_cross_peak].split(',')))           
            midi_associations['ball '+str(i)]['peak']['right cross'] = {}
            midi_associations['ball '+str(i)]['peak']['right cross']['channel'] = selected_config_midi_channels[ball_config_index_to_use[i]]
            midi_associations['ball '+str(i)]['peak']['right cross']['note_selection_mode'] = point_setups_note_selection_type[ui_point_index_for_right_cross_peak]
            midi_associations['ball '+str(i)]['peak']['right cross']['times_position_triggered'] = [-1]*len(settings.scale_to_use)
            midi_associations['ball '+str(i)]['peak']['right cross']['notes'] = notes_to_use
            midi_associations['ball '+str(i)]['peak']['right cross']['magnitude'] = midi_magnitude
        #midi_associations['ball '+str(i)]['peak']['right cross']['modulator'] = [['width',0,0], ['height',0,1]]

        midi_associations['ball '+str(i)]['catch'] = {}
        ui_point_index_for_mid_column_catch = mid_column_catch_path_point_configuration_index[ball_config_index_to_use[i]]
        if ui_point_index_for_mid_column_catch > 0:
            if point_setups_input_type[ui_point_index_for_mid_column_catch] == 'midi':
                notes_to_use = list(map(int,point_setups_single_line_input[ui_point_index_for_mid_column_catch].split(',')))
            midi_associations['ball '+str(i)]['catch']['mid column'] = {}
            midi_associations['ball '+str(i)]['catch']['mid column']['channel'] = selected_config_midi_channels[ball_config_index_to_use[i]]
            midi_associations['ball '+str(i)]['catch']['mid column']['note_selection_mode'] = point_setups_note_selection_type[ui_point_index_for_mid_column_catch]
            midi_associations['ball '+str(i)]['catch']['mid column']['times_position_triggered'] = [-1]*len(settings.scale_to_use)
            midi_associations['ball '+str(i)]['catch']['mid column']['notes'] = notes_to_use
            midi_associations['ball '+str(i)]['catch']['mid column']['magnitude'] = midi_magnitude
        #midi_associations['ball '+str(i)]['catch']['mid column']['modulator'] = [['width',0,0], ['height',0,1]]    
        #midi_associations['ball '+str(i)]['catch']['mid column'] = {}
        #midi_associations['ball '+str(i)]['catch']['mid column']['channel'] = selected_config_midi_channels[ball_config_index_to_use[i]]
        #midi_associations['ball '+str(i)]['catch']['mid column']['notes']['scale_type'] = 
        #midi_associations['ball '+str(i)]['catch']['mid column']['notes']['root'] = 
        #midi_associations['ball '+str(i)]['catch']['mid column']['notes'][''] = chord/scale/individual
        ui_point_index_for_left_column_catch = left_column_catch_path_point_configuration_index[ball_config_index_to_use[i]]
        if ui_point_index_for_left_column_catch > 0:
            if point_setups_input_type[ui_point_index_for_left_column_catch] == 'midi':
                notes_to_use = list(map(int,point_setups_single_line_input[ui_point_index_for_left_column_catch].split(',')))
            midi_associations['ball '+str(i)]['catch']['left column'] = {}
            midi_associations['ball '+str(i)]['catch']['left column']['channel'] = selected_config_midi_channels[ball_config_index_to_use[i]]
            midi_associations['ball '+str(i)]['catch']['left column']['note_selection_mode'] = point_setups_note_selection_type[ui_point_index_for_left_column_catch]
            midi_associations['ball '+str(i)]['catch']['left column']['times_position_triggered'] = [-1]*len(settings.scale_to_use)
            midi_associations['ball '+str(i)]['catch']['left column']['notes'] = notes_to_use
            midi_associations['ball '+str(i)]['catch']['left column']['magnitude'] = midi_magnitude
        #midi_associations['ball '+str(i)]['catch']['left column']['modulator'] = [['width',0,0], ['height',0,1]]
        ui_point_index_for_right_column_catch = right_column_catch_path_point_configuration_index[ball_config_index_to_use[i]]
        if ui_point_index_for_right_column_catch > 0:
            if point_setups_input_type[ui_point_index_for_right_column_catch] == 'midi':
                notes_to_use = list(map(int,point_setups_single_line_input[ui_point_index_for_right_column_catch].split(','))) 
            midi_associations['ball '+str(i)]['catch']['right column'] = {}
            midi_associations['ball '+str(i)]['catch']['right column']['channel'] = selected_config_midi_channels[ball_config_index_to_use[i]]
            midi_associations['ball '+str(i)]['catch']['right column']['note_selection_mode'] = point_setups_note_selection_type[ui_point_index_for_right_column_catch]
            midi_associations['ball '+str(i)]['catch']['right column']['times_position_triggered'] = [-1]*len(settings.scale_to_use)
            midi_associations['ball '+str(i)]['catch']['right column']['notes'] = notes_to_use
            midi_associations['ball '+str(i)]['catch']['right column']['magnitude'] = midi_magnitude
        #midi_associations['ball '+str(i)]['catch']['right column']['modulator'] = [['width',0,0], ['height',0,1]] 
        ui_point_index_for_mid_cross_catch = mid_cross_catch_path_point_configuration_index[ball_config_index_to_use[i]]
        if ui_point_index_for_mid_cross_catch > 0:
            if point_setups_input_type[ui_point_index_for_mid_cross_catch] == 'midi':
                notes_to_use = list(map(int,point_setups_single_line_input[ui_point_index_for_mid_cross_catch].split(',')))
            midi_associations['ball '+str(i)]['catch']['mid cross'] = {}
            midi_associations['ball '+str(i)]['catch']['mid cross']['channel'] = selected_config_midi_channels[ball_config_index_to_use[i]]
            midi_associations['ball '+str(i)]['catch']['mid cross']['note_selection_mode'] = point_setups_note_selection_type[ui_point_index_for_mid_cross_catch]
            midi_associations['ball '+str(i)]['catch']['mid cross']['times_position_triggered'] = [-1]*len(settings.scale_to_use)
            midi_associations['ball '+str(i)]['catch']['mid cross']['notes'] = notes_to_use
            midi_associations['ball '+str(i)]['catch']['mid cross']['magnitude'] = midi_magnitude
        #midi_associations['ball '+str(i)]['catch']['mid cross']['modulator'] = [['width',0,0], ['height',0,1]]
        ui_point_index_for_left_cross_catch = left_cross_catch_path_point_configuration_index[ball_config_index_to_use[i]]
        if ui_point_index_for_left_cross_catch > 0:
            if point_setups_input_type[ui_point_index_for_left_cross_catch] == 'midi':
                notes_to_use = list(map(int,point_setups_single_line_input[ui_point_index_for_left_cross_catch].split(',')))    
            midi_associations['ball '+str(i)]['catch']['left cross'] = {}
            midi_associations['ball '+str(i)]['catch']['left cross']['channel'] = selected_config_midi_channels[ball_config_index_to_use[i]]
            midi_associations['ball '+str(i)]['catch']['left cross']['note_selection_mode'] = point_setups_note_selection_type[ui_point_index_for_left_cross_catch]
            midi_associations['ball '+str(i)]['catch']['left cross']['times_position_triggered'] = [-1]*len(settings.scale_to_use)
            midi_associations['ball '+str(i)]['catch']['left cross']['notes'] = notes_to_use
            midi_associations['ball '+str(i)]['catch']['left cross']['magnitude'] = midi_magnitude
        #midi_associations['ball '+str(i)]['catch']['left cross']['modulator'] = [['width',0,0], ['height',0,1]]
        ui_point_index_for_right_cross_catch = right_cross_catch_path_point_configuration_index[ball_config_index_to_use[i]]
        if ui_point_index_for_right_cross_catch > 0:
            if point_setups_input_type[ui_point_index_for_right_cross_catch] == 'midi':
                notes_to_use = list(map(int,point_setups_single_line_input[ui_point_index_for_right_cross_catch].split(',')))           
            midi_associations['ball '+str(i)]['catch']['right cross'] = {}
            midi_associations['ball '+str(i)]['catch']['right cross']['channel'] = selected_config_midi_channels[ball_config_index_to_use[i]]
            midi_associations['ball '+str(i)]['catch']['right cross']['note_selection_mode'] = point_setups_note_selection_type[ui_point_index_for_right_cross_catch]
            midi_associations['ball '+str(i)]['catch']['right cross']['times_position_triggered'] = [-1]*len(settings.scale_to_use)
            midi_associations['ball '+str(i)]['catch']['right cross']['notes'] = notes_to_use
            midi_associations['ball '+str(i)]['catch']['right cross']['magnitude'] = midi_magnitude
        #midi_associations['ball '+str(i)]['catch']['right cross']['modulator'] = [['width',0,0], ['height',0,1]]

        midi_associations['ball '+str(i)]['throw'] = {}
        ui_point_index_for_mid_column_throw = mid_column_throw_path_point_configuration_index[ball_config_index_to_use[i]]
        if ui_point_index_for_mid_column_throw > 0:
            if point_setups_input_type[ui_point_index_for_mid_column_throw] == 'midi':
                notes_to_use = list(map(int,point_setups_single_line_input[ui_point_index_for_mid_column_throw].split(',')))
            midi_associations['ball '+str(i)]['throw']['mid column'] = {}
            midi_associations['ball '+str(i)]['throw']['mid column']['channel'] = selected_config_midi_channels[ball_config_index_to_use[i]]
            midi_associations['ball '+str(i)]['throw']['mid column']['note_selection_mode'] = point_setups_note_selection_type[ui_point_index_for_mid_column_throw]
            midi_associations['ball '+str(i)]['throw']['mid column']['times_position_triggered'] = [-1]*len(settings.scale_to_use)
            midi_associations['ball '+str(i)]['throw']['mid column']['notes'] = notes_to_use
            midi_associations['ball '+str(i)]['throw']['mid column']['magnitude'] = midi_magnitude
        #midi_associations['ball '+str(i)]['throw']['mid column']['modulator'] = [['width',0,0], ['height',0,1]]    
        #midi_associations['ball '+str(i)]['throw']['mid column'] = {}
        #midi_associations['ball '+str(i)]['throw']['mid column']['channel'] = selected_config_midi_channels[ball_config_index_to_use[i]]
        #midi_associations['ball '+str(i)]['throw']['mid column']['notes']['scale_type'] = 
        #midi_associations['ball '+str(i)]['throw']['mid column']['notes']['root'] = 
        #midi_associations['ball '+str(i)]['throw']['mid column']['notes'][''] = chord/scale/individual
        ui_point_index_for_left_column_throw = left_column_throw_path_point_configuration_index[ball_config_index_to_use[i]]
        if ui_point_index_for_left_column_throw > 0:
            if point_setups_input_type[ui_point_index_for_left_column_throw] == 'midi':
                notes_to_use = list(map(int,point_setups_single_line_input[ui_point_index_for_left_column_throw].split(',')))
            midi_associations['ball '+str(i)]['throw']['left column'] = {}
            midi_associations['ball '+str(i)]['throw']['left column']['channel'] = selected_config_midi_channels[ball_config_index_to_use[i]]
            midi_associations['ball '+str(i)]['throw']['left column']['note_selection_mode'] = point_setups_note_selection_type[ui_point_index_for_left_column_throw]
            midi_associations['ball '+str(i)]['throw']['left column']['times_position_triggered'] = [-1]*len(settings.scale_to_use)
            midi_associations['ball '+str(i)]['throw']['left column']['notes'] = notes_to_use
            midi_associations['ball '+str(i)]['throw']['left column']['magnitude'] = midi_magnitude
        #midi_associations['ball '+str(i)]['throw']['left column']['modulator'] = [['width',0,0], ['height',0,1]]
        ui_point_index_for_right_column_throw = right_column_throw_path_point_configuration_index[ball_config_index_to_use[i]]
        if ui_point_index_for_right_column_throw > 0:
            if point_setups_input_type[ui_point_index_for_right_column_throw] == 'midi':
                notes_to_use = list(map(int,point_setups_single_line_input[ui_point_index_for_right_column_throw].split(','))) 
            midi_associations['ball '+str(i)]['throw']['right column'] = {}
            midi_associations['ball '+str(i)]['throw']['right column']['channel'] = selected_config_midi_channels[ball_config_index_to_use[i]]
            midi_associations['ball '+str(i)]['throw']['right column']['note_selection_mode'] = point_setups_note_selection_type[ui_point_index_for_right_column_throw]
            midi_associations['ball '+str(i)]['throw']['right column']['times_position_triggered'] = [-1]*len(settings.scale_to_use)
            midi_associations['ball '+str(i)]['throw']['right column']['notes'] = notes_to_use
            midi_associations['ball '+str(i)]['throw']['right column']['magnitude'] = midi_magnitude
        #midi_associations['ball '+str(i)]['throw']['right column']['modulator'] = [['width',0,0], ['height',0,1]] 
        ui_point_index_for_mid_cross_throw = mid_cross_throw_path_point_configuration_index[ball_config_index_to_use[i]]
        if ui_point_index_for_mid_cross_throw > 0:
            if point_setups_input_type[ui_point_index_for_mid_cross_throw] == 'midi':
                notes_to_use = list(map(int,point_setups_single_line_input[ui_point_index_for_mid_cross_throw].split(',')))
            midi_associations['ball '+str(i)]['throw']['mid cross'] = {}
            midi_associations['ball '+str(i)]['throw']['mid cross']['channel'] = selected_config_midi_channels[ball_config_index_to_use[i]]
            midi_associations['ball '+str(i)]['throw']['mid cross']['note_selection_mode'] = point_setups_note_selection_type[ui_point_index_for_mid_cross_throw]
            midi_associations['ball '+str(i)]['throw']['mid cross']['times_position_triggered'] = [-1]*len(settings.scale_to_use)
            midi_associations['ball '+str(i)]['throw']['mid cross']['notes'] = notes_to_use
            midi_associations['ball '+str(i)]['throw']['mid cross']['magnitude'] = midi_magnitude
        #midi_associations['ball '+str(i)]['throw']['mid cross']['modulator'] = [['width',0,0], ['height',0,1]]
        ui_point_index_for_left_cross_throw = left_cross_throw_path_point_configuration_index[ball_config_index_to_use[i]]
        if ui_point_index_for_left_cross_throw > 0:
            if point_setups_input_type[ui_point_index_for_left_cross_throw] == 'midi':
                notes_to_use = list(map(int,point_setups_single_line_input[ui_point_index_for_left_cross_throw].split(',')))    
            midi_associations['ball '+str(i)]['throw']['left cross'] = {}
            midi_associations['ball '+str(i)]['throw']['left cross']['channel'] = selected_config_midi_channels[ball_config_index_to_use[i]]
            midi_associations['ball '+str(i)]['throw']['left cross']['note_selection_mode'] = point_setups_note_selection_type[ui_point_index_for_left_cross_throw]
            midi_associations['ball '+str(i)]['throw']['left cross']['times_position_triggered'] = [-1]*len(settings.scale_to_use)
            midi_associations['ball '+str(i)]['throw']['left cross']['notes'] = notes_to_use
            midi_associations['ball '+str(i)]['throw']['left cross']['magnitude'] = midi_magnitude
        #midi_associations['ball '+str(i)]['throw']['left cross']['modulator'] = [['width',0,0], ['height',0,1]]
        ui_point_index_for_right_cross_throw = right_cross_throw_path_point_configuration_index[ball_config_index_to_use[i]]
        if ui_point_index_for_right_cross_throw > 0:
            if point_setups_input_type[ui_point_index_for_right_cross_throw] == 'midi':
                notes_to_use = list(map(int,point_setups_single_line_input[ui_point_index_for_right_cross_throw].split(',')))           
            midi_associations['ball '+str(i)]['throw']['right cross'] = {}
            midi_associations['ball '+str(i)]['throw']['right cross']['channel'] = selected_config_midi_channels[ball_config_index_to_use[i]]
            midi_associations['ball '+str(i)]['throw']['right cross']['note_selection_mode'] = point_setups_note_selection_type[ui_point_index_for_right_cross_throw]
            midi_associations['ball '+str(i)]['throw']['right cross']['times_position_triggered'] = [-1]*len(settings.scale_to_use)
            midi_associations['ball '+str(i)]['throw']['right cross']['notes'] = notes_to_use
            midi_associations['ball '+str(i)]['throw']['right cross']['magnitude'] = midi_magnitude
        #midi_associations['ball '+str(i)]['throw']['right cross']['modulator'] = [['width',0,0], ['height',0,1]]'''

