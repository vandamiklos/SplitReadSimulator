import sys
import random
from badread import misc, fragment_lengths
import pysam
from scipy.stats import poisson


def read_fasta(args):
    fasta = {}
    fin = pysam.FastxFile(args.fasta)
    for line in fin:
        fasta[line.name] = line.sequence
    if len(fasta) == 0:
        raise ValueError("Empty fasta file")
    return fasta


def generate_duplication(args, ref, n_seqs, frag_lengths):
    chroms = list(ref.references)
    strand = ['forward', 'reverse']
    for n in range(n_seqs):
        seqs = []
        names = [f">duplication_"]
        c = random.choice(chroms)
        s = random.choice(strand)

        flen = []
        blk = 0
        pos = []
        while blk < 2:
            f = frag_lengths.get_fragment_length()
            if f < 15:
                continue
            if blk == 0:
                if 4*f < ref.get_reference_length(c) - int(1.5*f):
                    c = random.choice(chroms)
                    continue
                pos = random.randint(4*f, ref.get_reference_length(c) - int(1.5*f))
            blk += 1
            flen.append(f)

        seq1 = ref.fetch(c, pos, pos + flen[0]).upper()
        names.append(f"{c}:{pos}-{pos + flen[0]}")
        overlap = random.uniform(0.4, 1)

        if flen[0] < flen[1]:
            seq2 = ref.fetch(c, pos - (overlap * flen[0]), pos + flen[1] - (overlap * flen[0])).upper()
            names.append(f"{c}:{pos - overlap * flen[0]}-{pos + flen[1] - overlap * flen[0]}")
        if flen[0] > flen[1]:
            seq2 = ref.fetch(c, pos - (overlap * flen[1]), (pos + ((1 - overlap) * flen[1]))).upper()
            names.append(f"{c}:{pos - overlap * flen[1]}-{pos + (1 - overlap) * flen[1]}")

        if s == 'reverse':
            seq1 = misc.reverse_complement(seq1)
            seq2 = misc.reverse_complement(seq2)

        seqs.append(seq1)
        seqs.append(seq2)

        final_seq = "".join(seqs)
        final_name = "_".join(names)
        print(final_name)
        print(final_seq)

def generate_translocation(args, ref, n_seqs, frag_lengths):
    chroms = list(ref.references)
    strand = ['forward', 'reverse']
    for n in range(n_seqs):
        blocks = 2
        ins_seqs = []
        names = [f">translocation_"]
        blk = 0
        while blk < blocks:
            c = random.choice(chroms)
            s = random.choice(strand)
            flen = frag_lengths.get_fragment_length()
            if flen < 15:
                continue
            pos = random.randint(1, ref.get_reference_length(c) - flen)
            if pos + flen > ref.get_reference_length(c):
                continue  # happens rarely
            blk += 1
            seq = ref.fetch(c, pos, pos + flen).upper()
            if s == 'reverse':
                seq = misc.reverse_complement(seq)
            ins_seqs.append(seq)
            names.append(f"{c}:{pos}-{pos+flen}")
        final_seq = "".join(ins_seqs)
        final_name = "_".join(names)
        print(final_name)
        print(final_seq)


def generate_inversion(args, ref, n_seqs, frag_lengths):
    chroms = list(ref.references)
    strand = ['forward', 'reverse']
    for n in range(n_seqs):
        c = random.choice(chroms)
        s = random.choice(strand)
        flen = []
        blk = 0
        while blk < 3:
            f = frag_lengths.get_fragment_length()
            if f < 15:
                continue
            if blk == 0:
                if 4*f < ref.get_reference_length(c) - int(1.5*f):
                    c = random.choice(chroms)
                    continue
                pos = random.randint(4*f, ref.get_reference_length(c) - int(1.5*f))
            blk += 1
            flen.append(f)

        seq1 = ref.fetch(c, pos - flen[1] - flen[2], pos - flen[1]).upper()
        seq2 = ref.fetch(c, pos - flen[1], pos).upper()
        seq3 = ref.fetch(c, pos, pos + flen[0]).upper()

        if s == 'reverse':
            seq1 = misc.reverse_complement(seq1)
            seq3 = misc.reverse_complement(seq3)
        else:
            seq2 = misc.reverse_complement(seq2)

        ins_seqs = [seq1, seq2, seq3]
        names = [f">inversion_", f"{c}:{pos - flen[1] - flen[2]}-{pos-flen[1]}",
                 f"{c}:{pos-flen[1]}-{pos}",
                 f"{c}:{pos}-{pos+flen[0]}"]
        final_seq = "".join(ins_seqs)
        final_name = "_".join(names)
        print(final_name)
        print(final_seq)


def generate_deletion(args, ref, n_seqs, frag_lengths):
    chroms = list(ref.references)
    strand = ['forward', 'reverse']
    for n in range(n_seqs):
        c = random.choice(chroms)
        s = random.choice(strand)
        flen = []
        blk = 0
        while blk < 3:
            f = frag_lengths.get_fragment_length()
            if f < 15:
                continue
            if blk == 0:
                if 4*f < ref.get_reference_length(c) - int(1.5*f):
                    c = random.choice(chroms)
                    continue
                pos = random.randint(4*f, ref.get_reference_length(c) - int(1.5*f))
            blk += 1
            flen.append(f)

        seq1 = ref.fetch(c, (pos - flen[1] - flen[2]), (pos - flen[1])).upper()
        seq3 = ref.fetch(c, pos, (pos + flen[0])).upper()

        if s == 'reverse':
            seq1 = misc.reverse_complement(seq1)
            seq3 = misc.reverse_complement(seq3)

        seqs = [seq1, seq3]
        names = [f">deletion_", f"{c}:{pos - flen[1] - flen[2]}-{pos-flen[1]}",
                 f"{c}:{pos}-{pos+flen[0]}"]
        final_seq = "".join(seqs)
        final_name = "_".join(names)
        print(final_name)
        print(final_seq)


def generate_insertion(args, ref, n_seqs, frag_lengths):
    chroms = list(ref.references)
    strand = ['forward', 'reverse']
    for n in range(n_seqs):
        c = random.choice(chroms)
        s = random.choice(strand)
        flen = []
        blk = 0
        while blk < 3:
            f = frag_lengths.get_fragment_length()
            if f < 15:
                continue
            if blk == 0:
                if 4*f < ref.get_reference_length(c) - int(1.5*f):
                    c = random.choice(chroms)
                    continue
                pos = random.randint(int(4*f), ref.get_reference_length(c) - int(1.5*f))
            blk += 1
            flen.append(f)

        seq1 = ref.fetch(c, pos - flen[1] - flen[2], pos - flen[1]).upper()
        seq2 = ref.fetch(c, pos - flen[1], pos).upper()
        seq3 = ref.fetch(c, pos, pos + flen[0]).upper()

        if s == 'reverse':
            seq1 = misc.reverse_complement(seq1)
            seq2 = misc.reverse_complement(seq2)
            seq3 = misc.reverse_complement(seq3)


        seqs = [seq1, seq2, seq3]
        names = [f">insertion_", f"{c}:{pos - flen[1] - flen[2]}-{pos-flen[1]}",
                 f"{c}:{pos-flen[1]}-{pos}",
                 f"{c}:{pos}-{pos+flen[0]}"]
        final_seq = "".join(seqs)
        final_name = "_".join(names)
        print(final_name)
        print(final_seq)


def generate_svs(args):
    ref = pysam.FastaFile(args.reference)

    print(f"Generating {args.number} SVs", file=sys.stderr)

    frag_lengths = fragment_lengths.FragmentLengths(args.mean_block_len, args.std_block_len)

    generate_duplication(args, ref, args.number, frag_lengths)
    generate_deletion(args, ref, args.number, frag_lengths)
    generate_insertion(args, ref, args.number, frag_lengths)
    generate_inversion(args, ref, args.number, frag_lengths)
    generate_translocation(args, ref, args.number, frag_lengths)

    print(f"Done", file=sys.stderr)