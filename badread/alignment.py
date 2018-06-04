"""
Copyright 2018 Ryan Wick (rrwick@gmail.com)
https://github.com/rrwick/Badread

The version is stored here in a separate file so it can exist in only one place.
http://stackoverflow.com/questions/458550

This file is part of Badread. Badread is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version. Badread is distributed
in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
details. You should have received a copy of the GNU General Public License along with Badread.
If not, see <http://www.gnu.org/licenses/>.
"""

import collections
import re
import sys
from .misc import get_open_func


class Alignment(object):

    def __init__(self, paf_line):
        line_parts = paf_line.strip().split('\t')

        self.read_name = line_parts[0]
        self.read_start = int(line_parts[2])
        self.read_end = int(line_parts[3])
        self.strand = line_parts[4]

        self.ref_name = line_parts[5]
        self.ref_length = int(line_parts[6])
        self.ref_start = int(line_parts[7])
        self.ref_end = int(line_parts[8])

        self.matching_bases = int(line_parts[9])
        self.num_bases = int(line_parts[10])
        self.percent_identity = 100.0 * self.matching_bases / self.num_bases

        self.cigar, self.alignment_score = None, None
        for part in line_parts:
            if part.startswith('cg:Z:'):
                self.cigar = part[5:]
            if part.startswith('AS:i:'):
                self.alignment_score = int(part[5:])
        if self.cigar is None:
            sys.exit('Error: no CIGAR string found')
        if self.alignment_score is None:
            sys.exit('Error: no alignment score')

        self.max_indel = 0
        self.cigar_parts = re.findall(r'\d+\w', self.cigar)
        for cigar_part in self.cigar_parts:
            num = int(cigar_part[:-1])
            letter = cigar_part[-1]
            if (letter == 'I' or letter == 'D') and num > self.max_indel:
                self.max_indel = num

        # I want the CIGAR in terms of the read, so I need to flip it if it aligned to the other
        # strand of the reference.
        if self.strand == '-':
            self.cigar_parts = self.cigar_parts[::-1]

    def __repr__(self):
        return self.read_name + ':' + str(self.read_start) + '-' + str(self.read_end) + \
               '(' + self.strand + '),' + \
               self.ref_name + ':' + str(self.ref_start) + '-' + str(self.ref_end) + \
               '(' + ('%.3f' % self.percent_identity) + '%)'


def load_alignments(filename, max_alignments=None):
    i = 0
    print('Loading alignments', end='', file=sys.stderr, flush=True)
    all_alignments = collections.defaultdict(list)
    with get_open_func(filename)(filename, 'rt') as paf_file:
        for line in paf_file:
            a = Alignment(line)
            all_alignments[a.read_name].append(a)
            i += 1
            if i % 1000 == 0:
                print('.', end='', file=sys.stderr, flush=True)
            if i == max_alignments:
                break
    print('', file=sys.stderr, flush=True)
    i = 0
    print('Choosing best alignment per read', end='', file=sys.stderr, flush=True)
    best_alignments = []
    for read_name, alignments in all_alignments.items():
        best = sorted(alignments, key=lambda x: x.alignment_score)[-1]
        if best.num_bases > 1000 and best.percent_identity > 80.0:
            best_alignments.append(best)
            i += 1
            if i % 1000 == 0:
                print('.', end='', file=sys.stderr, flush=True)
    print('', file=sys.stderr, flush=True)
    return best_alignments


def align_sequences(read_seq, ref_seq, alignment):
    read, ref = [], []
    read_pos, ref_pos = 0, 0
    errors_per_read_pos = [0] * len(read_seq)
    alignment.insertions, alignment.deletions, alignment.mismatches = 0, 0, 0
    for c in alignment.cigar_parts:
        cigar_type = c[-1]
        cigar_size = int(c[:-1])
        if cigar_type == 'M':
            read.append(read_seq[read_pos:read_pos+cigar_size])
            ref.append(ref_seq[ref_pos:ref_pos+cigar_size])
            for i in range(cigar_size):
                if read_seq[read_pos+i] != ref_seq[ref_pos+i]:
                    errors_per_read_pos[read_pos+i] += 1
                    alignment.mismatches += 1
            read_pos += cigar_size
            ref_pos += cigar_size
        if cigar_type == 'I':
            read.append(read_seq[read_pos:read_pos+cigar_size])
            ref.append('-' * cigar_size)
            for i in range(cigar_size):
                errors_per_read_pos[read_pos+i] += 1
            alignment.insertions += cigar_size
            read_pos += cigar_size
        if cigar_type == 'D':
            read.append('-' * cigar_size)
            ref.append(ref_seq[ref_pos:ref_pos+cigar_size])
            errors_per_read_pos[read_pos] += cigar_size
            alignment.deletions += cigar_size
            ref_pos += cigar_size
    return ''.join(read), ''.join(ref), errors_per_read_pos