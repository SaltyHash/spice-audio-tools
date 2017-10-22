"""Run an audio file through your Spice model to hear what it sounds like."""

import argparse
import numpy as np
import os
import struct
import sys
import wave


def spice2sound(input_audio_file_path, spice_model_path, output_audio_file_path):
    # Make sure input files exist
    if not os.path.exists(input_audio_file_path):
        print('ERROR: Input audio file "{}" does not exist.'.format(input_audio_file_path))
        return 1
    if not os.path.exists(spice_model_path):
        print('ERROR: Spice model file "{}" does not exist.'.format(spice_model_path))
        return 1

    # Read in the input audio file info and frames
    # TODO: Support more audio file types?
    with wave.open(input_audio_file_path, 'rb') as input_audio_file:
        channel_cnt, sample_width, framerate, frame_cnt, _, _ = input_audio_file.getparams()
        input_audio_frames = input_audio_file.readframes(frame_cnt)

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

    # TODO: Someday, when PySpice 1.2 rolls out on PyPI...
    # https://pyspice.fabrice-salvaire.fr/examples/ngspice-shared/external-source.html
    # # Parse the model and simulate
    # model     = SpiceParser(path=spice_model_path)
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

    return 0


if __name__ == '__main__':
    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('input_audio',  metavar='input-audio',
                        help='path to the input audio file')
    parser.add_argument('spice_model',  metavar='spice-model',
                        help='path to the spice model')
    parser.add_argument('output_audio', metavar='output-audio',
                        help='path to save the output audio file')
    args = parser.parse_args()

    sys.exit(spice2sound(args.input_audio, args.spice_model, args.output_audio))
