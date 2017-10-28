"""Run an audio file through a Spice circuit to hear what it sounds like."""

import argparse
import numpy as np
import os
import struct
import sys
import tempfile
import wave


def rms(v):
    """Returns the RMS voltage of the rows of the v array."""
    return np.sqrt(np.mean(np.power(v, 2), axis=1))


def spice2sound(input_audio_file_path, spice_circuit_path, output_audio_file_path,
                channel=None, input_node='input', output_node='output', sim_time=None, xtrtol=7.0):
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
    sim_time     = max_sim_time if not sim_time else min(sim_time, max_sim_time)

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
    input_audio_rms    = np.max(rms(input_audio_values))
    print(input_audio_rms)

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

    # Open a temporary directory
    with tempfile.TemporaryDirectory(prefix='spice2sound-') as tmp_dir:
        tmp_input_values_path  = os.path.join(tmp_dir, 'input_values')
        tmp_output_values_path = os.path.join(tmp_dir, 'output_values')
        tmp_spice_circuit_path = os.path.join(tmp_dir, 'spice.cir')

        # Save the input values to tmp file
        t = 0
        with open(tmp_input_values_path, 'w') as input_values_file:
            for value in input_audio_values[1 if (channel_cnt > 1 and channel == 'right') else 0]:
                input_values_file.write('{:.6e} {:.4f}\n'.format(t, value))
                t += 1 / framerate

        # Add lines to Spice circuit for simulation
        with open(spice_circuit_path, 'rt') as spice_circuit_file:
            spice_circuit = spice_circuit_file.read()
        spice_circuit += '\n'.join((
            '',
            'A1 %v([{}]) filesrc'.format(input_node),
            '',
            '.control',
            'save v({})'.format(output_node),
            'set xtrtol={}'.format(xtrtol),     # Set simulation quality
            'tran {} {}'.format(1 / framerate, sim_time),
            'linearize',        # Transient outputs are not perfectly synced to timestep; this fixes that problem
            'wrdata {} v({})'.format(tmp_output_values_path, output_node),
            '.endc',
            '',
            '.options noacct'   # Don't print all that netlist stuff
            '',
            '.model filesrc filesource (file="{}"'.format(tmp_input_values_path),
            '+    amploffset=[0] amplscale=[1] amplstep=false',
            '+    timeoffset=0   timescale=1   timerelative=false)'
        ))

        # Save the modified spice circuit to tmp file
        with open(tmp_spice_circuit_path, 'wt') as spice_circuit_file:
            spice_circuit_file.write(spice_circuit)

        # Run the simulation!
        os.system('ngspice -b {}'.format(tmp_spice_circuit_path))

        # Read the results from the tmp output file
        with open(tmp_output_values_path, 'rt') as output_values_file:
            output_values = [float(line.split()[1]) for line in output_values_file.readlines()]

    # Discard output result at t=0
    output_values.pop(0)
    # Normalize the values to [-1.0, 1.0]
    output_values = np.array(output_values).reshape((1, -1))
    output_values = output_values / np.max(np.abs(output_values))

    # Scale the output values to match the input audio RMS
    output_values = output_values * input_audio_rms / np.max(rms(output_values))
    print(rms(output_values))

    # Write the output values to the output wav file
    with wave.open(output_audio_file_path, 'wb') as output_audio_file:
        # 1 channel, 2 bytes per frame, framerate, frame count
        output_audio_file.setparams((1, 2, framerate, output_values.shape[1], 'NONE', 'not compressed'))
        output_audio_file.writeframes(struct.pack(
            '<{}h'.format(output_values.shape[1]),
            *(output_values[0] * 32767).astype(int)
        ))

    return 0


if __name__ == '__main__':
    # Build argument parser
    parser = argparse.ArgumentParser(description=__doc__)
    # - Required arguments
    parser.add_argument('input_audio',   metavar='input-audio',
                        help='path to the input audio file')
    parser.add_argument('spice_circuit', metavar='spice-circuit',
                        help='path to the Spice circuit')
    parser.add_argument('output_audio',  metavar='output-audio',
                        help='path to save the output audio file')
    # - Optional arguments
    parser.add_argument(
        '--channel', choices=['left', 'right'], type=str.lower,
        help='''if the input audio file is stereo, this selects which audio channel to use
            (both channels are used by default)'''
    )
    parser.add_argument(
        '--input-node', metavar='NODE', default='input',
        help='the Spice circuit\'s input node (defaults to "input")'
    )
    parser.add_argument(
        '--output-node', metavar='NODE', default='output',
        help='the Spice circuit\'s output node (defaults to "output")'
    )
    parser.add_argument(
        '--sim-time', metavar='SECONDS', type=float,
        help='limit how many seconds of audio to simulate (defaults to length of input audio file)'
    )
    parser.add_argument(
        '--xtrtol', metavar='VALUE', default=7.0, type=float,
        help='''sets simulation quality. Lower values give higher quality but lower speed.
            Defaults to 7. Range is [1, 7]. Set lower if convergence errors occur.
            See ngspice documentation for details.'''
    )
    # Parse arguments
    args = parser.parse_args()

    sys.exit(spice2sound(
        args.input_audio,
        args.spice_circuit,
        args.output_audio,
        args.channel,
        args.input_node,
        args.output_node,
        args.sim_time,
        args.xtrtol
    ))
