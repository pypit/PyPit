#!/usr/bin/env python
#
# See top-level LICENSE file for Copyright information
#
# -*- coding: utf-8 -*-
"""
Trace slit edges for a set of images.
"""

def parser():

    import argparse
    from pypeit.spectrographs.util import valid_spectrographs

    parser = argparse.ArgumentParser()

    # Require either a pypeit file or a fits file 
    inp = parser.add_mutually_exclusive_group(required=True)
    inp.add_argument('-f', '--pypeit_file', default=None, type=str, help='PypeIt reduction file')
    inp.add_argument('-t', '--trace_file', default=None, type=str, help='Image to trace')

    parser.add_argument('-g', '--group', default=None,
                        help='If providing a pypeit file, use the trace images for this '
                             'calibration group.  If None, use the first calibration group.')
    parser.add_argument('-d', '--detector', default=None, type=int,
                        help='Only analyze the specified detector; otherwise analyze all.')
    parser.add_argument('-s', '--spectrograph', default=None, type=str,
                        help='A valid spectrograph identifier, which is only used if providing'
                             'files directly: {0}'.format(', '.join(valid_spectrographs())))
    parser.add_argument('-b', '--binning', default=None, type=str,
                        help='Image binning in spectral and spatial directions.  Only used if'
                             'providing files directly; default is 1,1.')
    parser.add_argument('-p', '--redux_path', default=None,
                        help='Path to top-level output directory.  '
                             'Default is the current working directory.')
    parser.add_argument('-m', '--master_dir', default='Masters',
                        help='Name for directory in output path for Master file(s) relative '
                             'to the top-level directory.')
    parser.add_argument('-o', '--overwrite', default=False, action='store_true',
                        help='Overwrite any existing files/directories')

    parser.add_argument('--debug', default=False, action='store_true', help='Run in debug mode.')

    parser.add_argument('-n', '--use_new', default=False, action='store_true',
                        help='Use the new code.')

    return parser.parse_args()


def main(args):

    import time
    import os
    import numpy as np
    from pypeit.spectrographs.util import load_spectrograph
    from pypeit import traceslits, traceimage, edgetrace
    from pypeit.pypeit import PypeIt
    from pypeit.core import parse

    if args.pypeit_file is not None:
        pypeit_file = args.pypeit_file
        if not os.path.isfile(pypeit_file):
            raise FileNotFoundError('File does not exist: {0}'.format(pypeit_file))
        pypeit_file = os.path.abspath(pypeit_file)
        redux_path = os.path.abspath(os.path.split(pypeit_file)[0]
                                     if args.redux_path is None else args.redux_path)

        rdx = PypeIt(pypeit_file, redux_path=redux_path)
        # Save the spectrograph
        spec = rdx.spectrograph
        # Get the calibration group to use
        group = np.unique(rdx.fitstbl['calib'])[0] if args.group is None else args.group
        if group not in np.unique(rdx.fitstbl['calib']):
            raise ValueError('Not a valid calibration group: {0}'.format(group))
        # Find the rows in the metadata table with trace frames in the
        # specified calibration group
        tbl_rows = rdx.fitstbl.find_frames('trace', calib_ID=int(group), index=True)
        # Master keyword
        master_key_base = '_'.join(rdx.fitstbl.master_key(tbl_rows[0]).split('_')[:2])
        # Save the binning
        binning = rdx.fitstbl['binning'][tbl_rows[0]]
        # Save the full file paths
        files = rdx.fitstbl.frame_paths(tbl_rows)
        # Trace image processing parameters
        proc_par = rdx.caliBrate.par['traceframe']
        # Slit tracing parameters
        trace_par = rdx.caliBrate.par['slitedges'] if args.use_new else rdx.caliBrate.par['slits']
    else:
        spec = load_spectrograph(args.spectrograph)
        master_key_base = 'A_1'
        binning = '1,1' if args.binning is None else args.binning
        if not os.path.isfile(args.trace_file):
            raise FileNotFoundError('File does not exist: {0}'.format(args.trace_file))
        files = [os.path.abspath(args.trace_file)]
        redux_path = os.path.abspath(os.path.split(files[0])[0]
                                     if args.redux_path is None else args.redux_path)
        par = spec.default_pypeit_par()
        proc_par = par['calibrations']['traceframe']
        trace_par = par['calibrations']['slitedges'] if args.use_new \
                        else par['calibrations']['slits']
    
    detectors = np.arange(spec.ndet)+1 if args.detector is None else [args.detector]
    master_dir = os.path.join(redux_path, args.master_dir)
    for det in detectors:
        # Master keyword for output file name
        master_key = '{0}_{1}'.format(master_key_base, str(det).zfill(2))

        # Build the trace image
        traceImage = traceimage.TraceImage(spec, files=files, det=det, par=proc_par)
        traceImage.build_image()

#        traceImage = traceimage.TraceImage(spec, files=files, det=det, par=proc_par)
#        traceImage.process(bias_subtract='overscan', trim=True, apply_gain=True)

        # Platescale
        plate_scale = parse.parse_binning(binning)[1]*spec.detector[det-1]['platescale']

        # Trace the slit edges
        if args.use_new:
            t = time.perf_counter()
            try:
                edges = edgetrace.EdgeTraceSet(spec, trace_par, master_key=master_key,
                                               master_dir=master_dir, img=traceImage, det=det,
                                               auto=True)
                print('Tracing for detector {0} finished in {1} s.'.format(det, time.perf_counter()-t))
                edges.save()
            except:
                pass
        else:
            t = time.perf_counter()
            traceSlits = traceslits.TraceSlits(spec, trace_par, det=det, master_key=master_key,
                                               master_dir=master_dir)
            traceSlits.run(traceImage.image, binning, plate_scale=plate_scale, write_qa=False)
            print('Tracing for detector {0} finished in {1} s.'.format(det, time.perf_counter()-t))
            traceSlits.save(traceImage=traceImage)

    return 0


