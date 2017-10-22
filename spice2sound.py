"""Run an audio file through your Spice model to hear what it sounds like."""

import argparse
import numpy as np
import os
import struct
import sys
import wave


def spice2sound(input_audio_file_path, spice_circuit_path, output_audio_file_path,
                sim_time=None):
    # Make sure input files exist
    if not os.path.exists(input_audio_file_path):
        print('ERROR: Input audio file "{}" does not exist.'.format(input_audio_file_path))
        return 1
    if not os.path.exists(spice_circuit_path):
        print('ERROR: Spice circuit file "{}" does not exist.'.format(spice_circuit_path))
        return 1

    # Read in the input audio file info and frames
    # TODO: Support more audio file types?
    with wave.open(input_audio_file_path, 'rb') as input_audio_file:
        channel_cnt, sample_width, framerate, frame_cnt, _, _ = input_audio_file.getparams()
        input_audio_frames = input_audio_file.readframes(frame_cnt)
    max_sim_time = frame_cnt / framerate
    sim_time = max_sim_time if not sim_time else min(sim_time, max_sim_time)

    # Convert raw wav frames into values
    fmt = '<{}'.format(channel_cnt * frame_cnt)
    if sample_width == 1:       # 8-bit samples
        fmt += 'b'
    elif sample_width == 2:     # 16-bit samples
        fmt += 'h'
    elif sample_width == 4:     # 32-bit samples
        fmt += 'i'
    else:
        print('ERROR: {}-bit sample width is unsupported.'.format(sample_width*8))
        return 1
    # Get 1-D array of values in the range [-1.0, 1.0]
    input_audio_values = np.array(struct.unpack_from(fmt, input_audio_frames))
    input_audio_values = input_audio_values / (2 ** (8 * sample_width) - 1)
    # Make values accessible by [channel][frame]
    input_audio_values = input_audio_values.reshape(-1, channel_cnt).T
    print(input_audio_values.shape)

    # TODO: Someday, when PySpice 1.2 rolls out on PyPI:
    # https://pyspice.fabrice-salvaire.fr/examples/ngspice-shared/external-source.html
    # # Parse the model and simulate
    # model     = SpiceParser(path=spice_circuit_path)
    # circuit   = model.build_circuit(ground=0)
    # circuit.V('input', 'input', circuit.gnd, 'DC 0 external')
    # print(circuit)
    # simulator = circuit.simulator(simulator='ngspice-shared', ngspice_shared=left_wav_spice_source)
    # simulator.save('output')
    # print(simulator)
    # analysis = simulator.transient(
    #     step_time=1 / framerate,
    #     end_time=frame_cnt / framerate,
    #     probes=['output'])
    # print(analysis['output'].shape)

    # Save the input values to file
    with open('./input_values', 'w') as input_values_file:
        t = 0
        for value in input_audio_values[0]:
            input_values_file.write('{:.6e} {:.4f}\n'.format(t, value))
            t += 1 / framerate

    # Add lines to Spice circuit for simulation
    with open(spice_circuit_path, 'rt') as spice_circuit_file:
        spice_circuit = spice_circuit_file.read()
    spice_circuit += '\n'.join((
        '',
        'A1 %v([input]) filesrc',
        '',
        '.control',
        'save v(output)',
        'tran {} {}'.format(1 / framerate, sim_time),
        'wrdata output_values v(output)',
        '.endc',
        '',
        '.model filesrc filesource (file="input_values" amploffset=[0] amplscale=[1]',
        '+                          timeoffset=0 timescale=1',
        '+                          timerelative=false amplstep=false)',
    ))
    with open('./spice.cir', 'wt') as spice_circuit_file:
        spice_circuit_file.write(spice_circuit)

    return_code = os.system('ngspice -b {}'.format('./spice.cir'))
    print('error!' if return_code else 'success!')

    return 0


if __name__ == '__main__':
    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--sim-time', type=float,
                        help='limit how many seconds of audio to simulate')
    parser.add_argument('input_audio',   metavar='input-audio',
                        help='path to the input audio file')
    parser.add_argument('spice_circuit', metavar='spice-model',
                        help='path to the Spice circuit')
    parser.add_argument('output_audio',  metavar='output-audio',
                        help='path to save the output audio file')
    args = parser.parse_args()

    sys.exit(spice2sound(
        args.input_audio,
        args.spice_circuit,
        args.output_audio,
        args.sim_time
    ))
