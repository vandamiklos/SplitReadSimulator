from sys import stderr
import pandas as pd
import numpy as np
import pysam
import matplotlib.pyplot as plt
import seaborn as sns

"""
inputs
------
the .bed file of mappings from aligners
the .fastq reads generated by SplitReadSimulator
output prefix

outputs
-------
graphs showing:
 numbers of mappings vs expected mappings
 histogram of alignment sizes
 summary report with overall precision and recall of mappings
 scatter plot of alignment size vs mapping precision

"""

import faulthandler
faulthandler.enable()
class InsEvent:
    def __init__(self, info):
        info = info.replace('__', ' ')
        parts = info.split(' ')
        if parts[1] in ['junk_seq', 'random_seq']:
            return
        self.qname = parts[0]
        self.ins_blocks = None
        blocks = parts[2].split('_')
        self.blocks = []
        for k in blocks:
            a = k.split(':')
            chrom = a[0]
            start, end = a[1].split('-')
            self.blocks.append((chrom, int(start), int(end)))
        self.identity = float(parts[-1].split('=')[1][:-1])

    def __len__(self):
        return len(self.blocks)

    def get_ins_blocks(self):
        return self.blocks


def load_frag_info(pth):
    ins_events = {}
    fq = pysam.FastxFile(pth)
    n=0
    for r in fq:
        name = r.__str__().split('\n')[0][1:]
        if 'deletion' or 'translocation' or 'insertion' or 'duplication' or 'inversion' in name and 'junk_seq' not in name and 'random_seq' not in name:
            ie = InsEvent(name)
            ins_events[ie.qname] = ie
            n += len(ie.get_ins_blocks())
    return ins_events, n


def analyse_ins_numbers(df, ins_events, prefix, n, figures):
    res = []
    for k, grp in df.groupby('qname'):
        name = k.split('.')[0]
        if name in ins_events:
            res.append({'expected': len(ins_events[name]), 'mapped': len(grp)})

    d = pd.DataFrame.from_records(res)
    print(d.head())
    max_expect = d['expected'].max()
    u = d['expected'].unique().tolist()
    u.sort()

    if figures:
        fig, axes = plt.subplots(len(u), 1, figsize=(7, len(u)*2), sharex=True)
        for i in range(len(u)):
            dd = d[d['expected'] == u[i]]
            if dd.empty:
                continue
            axes[i].set_title(f'Expected alignments = {u[i]}')
            sns.histplot(dd, x='mapped', ax=axes[i], discrete=True)
            axes[i].axvline(x=u[i], ls='--', color='r')
        plt.tight_layout()
        plt.savefig(prefix + 'mappings_vs_expected.png', dpi=600)
        plt.close()

        scale = 0.01
        min_expect = d['expected'].min()
        line = {'expected': range(min_expect, max_expect), 'mapped': range(min_expect, max_expect)}
        counts = d.groupby(['expected', 'mapped']).size().reset_index(name='size')
        counts['size'] = counts['size'] * scale
        plt.scatter(data=counts, x='expected', y='mapped', alpha=0.8, s='size', linewidths=0)
        plt.plot(line['expected'], line['mapped'], color='r', alpha=0.5, ls='--')
        plt.tight_layout()
        plt.savefig(prefix + 'mappings_vs_expected_scatter.png', dpi=600)
        plt.close()

    def match_func(block_A, block_B):
        if abs(block_A[1] - block_B[1]) < 50 and abs(block_A[2] - block_B[2]) < 50:
            return True
        return False
    # test with reset index
    df = df.reset_index()
    fp = np.zeros(len(df))
    tp = np.zeros(len(df))
    ins_aln_idx = np.zeros(len(df))

    all_res = []
    fn={}
    for k, grp in df.groupby('qname'):
        name = k.split('.')[0]
        if name in ins_events:
            e = ins_events[name]
            target_ins_alns = e.get_ins_blocks()
            alns = list(zip(grp['chrom'], grp['rstart'], grp['rend'], grp.index, grp['mapq']))
            if target_ins_alns:
                for ia in alns:
                    ins_aln_idx[ia[3]] = 1
                r = {'qname': k, 'n_target': len(target_ins_alns), 'n_ins': len(alns), 'tp': 0, 'fp': 0, 'fn': 0}
                fn_alns=[]
                for blockA in target_ins_alns:
                    for blockB in alns:
                        if match_func(blockA, tuple(blockB)):
                            break
                    else:
                        r['fn'] += 1
                        fn_alns.append(blockA)

                for blockB in alns:
                    for blockA in target_ins_alns:
                        if match_func(blockA, tuple(blockB)):
                            r['tp'] += 1
                            assert tp[blockB[3]] == 0
                            tp[blockB[3]] = 1
                            break
                    else:
                        r['fp'] += 1
                        assert fp[blockB[3]] == 0
                        fp[blockB[3]] = 1
                all_res.append(r)
            fn[k] = fn_alns

    fn_res=[]
    for qname, d in fn.items():
        temp = []
        for index, pos in enumerate(d):
            rd = {'qname': qname,
                  'chrom': pos[0],
                  'qstart': pos[1],
                  'qend': pos[2],
                  'fn': 1,
                  'aln_size': pos[2] - pos[1]}
            temp.append(rd)
        fn_res+=temp

    df1 = pd.DataFrame.from_records(fn_res).sort_values(['qname', 'qstart'])

    df_res = pd.DataFrame(all_res)
    df_res.to_csv(prefix + 'benchmark_res.csv', sep='\t', index=False)
    df['tp'] = tp
    df['fp'] = fp
    df['alns'] = ins_aln_idx

    df_fn = pd.concat([df1, df], axis=0, ignore_index=True)
    df_fn = pd.merge(df_fn, df_res[['qname', 'n_target']], how='left', on='qname')
    # df_fn.fillna(0, inplace=True)
    df_fn.sort_values(['qname', 'qstart'])
    # numeric_cols = df_fn.select_dtypes(include=['number'])
    # df_fn[numeric_cols.columns] = numeric_cols.astype(int)
    df_fn.to_csv(prefix + 'benchmark_res_fn.csv', sep='\t', index=False)

    d = df[df['alns'] == 1]
    assert (len(d) == df_res['tp'].sum() + df_res['fp'].sum())
    prec = round(df_res['tp'].sum() / (df_res['tp'].sum() + df_res['fp'].sum()), 4)
    recall = round(df_res['tp'].sum() / (df_res['tp'].sum() + df_res['fn'].sum()), 4)
    f = round(2 * df_res['tp'].sum() / (2 * df_res['tp'].sum() + df_res['fn'].sum()), 4)


    with open(prefix + 'stats.txt', 'w') as st:
        st.write('precision\trecall\tf-score\tquery_n\ttarget_n\n')
        st.write(f'{prec}\t{recall}\t{f}\t{len(d)}\t{n}\n')
    d.to_csv(prefix + 'mappings_labelled.csv', sep='\t', index=False)

    if figures:
        # assess mapping accuracy by alignment length
        plt.figure()
        plt.hist(d['aln_size'], bins=np.arange(0, 800, 25))
        plt.ylabel('count')
        plt.xlabel('alignment size')
        plt.tight_layout()
        plt.savefig(prefix + 'aln_sizes.png', dpi=600)
        # plt.show()
        plt.close()

        # size bins
        bins = []
        base = 25
        for i in d['aln_size']:
            bins.append(base * round(i/base))  # round to nearest 50
        d = d.assign(bins=bins)


        bin_precison = []
        bin_id = []
        s = []
        for bid, b in d.groupby('bins'):
            if len(b) < 5:
                continue
            s.append(len(b) * scale)
            bin_precison.append(b['tp'].sum() / (b['tp'].sum() + b['fp'].sum()))
            bin_id.append(bid)

        plt.plot(bin_id, bin_precison, alpha=0.8)
        plt.scatter(bin_id, bin_precison, s=s, alpha=0.25, linewidths=0)
        plt.xscale("log")
        plt.xlabel('Alignment size')
        plt.ylabel('Precision')
        plt.ylim(0, 1.1)
        plt.tight_layout()
        plt.savefig(prefix + 'size_vs_precision.png', dpi=600)
        # plt.show()
        plt.close()

        #mapq bins
        bin_precison2 = []
        bin_id2 = []
        s2 = []
        for bid, b in d.groupby('mapq'):
            if len(b) < 5:
                continue
            s2.append(len(b) * scale)
            bin_precison2.append(b['tp'].sum() / (b['tp'].sum() + b['fp'].sum()))
            bin_id2.append(bid)

        plt.plot(bin_id2, bin_precison2, alpha=0.8)
        plt.scatter(bin_id2, bin_precison2, s=s2, alpha=0.5, linewidths=0)
        # plt.xlim(0, 2000)
        plt.xlabel('MapQ')
        plt.ylabel('Precision')
        plt.ylim(0, 1.1)
        plt.tight_layout()
        plt.savefig(prefix + 'mapq_vs_precision.png', dpi=600)
        plt.close()


        # cummulative graph - aln size
        bin_fp = []
        bin = []
        fp = 0
        s_fp=[]
        for bid, b in d.groupby('bins'):
            bin_fp.append(fp / n * 100)
            bin.append(bid)
            fp += b['fp'].sum()
            s_fp.append(len(b)*scale)

        plt.plot(bin, bin_fp)
        plt.scatter(bin, bin_fp, s=s_fp, alpha=0.25, linewidths=0)
        plt.xlabel('Alignment size')
        plt.ylabel('False positive %')
        plt.tight_layout()
        plt.savefig(prefix + 'aln_size_vs_wrong.png', dpi=600)
        plt.close()


        # cummulative graph - mapq
        bin_wrong = []
        bin_w = []
        wrong = 0
        s=[]
        for bid, b in d.groupby('mapq'):
            bin_wrong.append(wrong / n)
            bin_w.append(bid)
            wrong += b['fp'].sum()
            s.append(len(b)*scale)

        plt.plot(bin_w, bin_wrong)
        plt.scatter(bin_w, bin_wrong, s=s, alpha=0.5, linewidths=0)
        plt.xlabel('MapQ')
        plt.ylabel('False positive %')
        plt.tight_layout()
        plt.savefig(prefix + 'mapq_vs_fp.png', dpi=600)
        plt.close()


        bins=[]
        for i in df_fn['aln_size']:
            bins.append(base * round(i/base))  # round to nearest 50
        df_fn = df_fn.assign(bins=bins)

        bin_wrong = []
        bin_w = []
        wrong = 0
        s=[]
        for bid, b in df_fn.groupby('bins'):
            bin_wrong.append(wrong / n)
            bin_w.append(bid)
            wrong += b['fn'].sum()
            s.append(len(b)*scale)

        plt.plot(bin_w, bin_wrong)
        plt.scatter(bin_w, bin_wrong, s=s, alpha=0.25, linewidths=0)
        plt.xlabel('MapQ')
        plt.ylabel('False negative %')
        plt.tight_layout()
        plt.savefig(prefix + 'fn_bins.png', dpi=600)
        plt.close()


        # precision - recall curve (aln size)
        recall = []
        precision = []
        tp = 0
        fp = 0
        fn = 0
        s=[]
        for i, b in df_fn.groupby('bins'):
            tp += b['tp'].sum()
            fp += b['fp'].sum()
            fn += b['fn'].sum()
            if tp+fp == 0 or tp+fn == 0:
                continue
            precision.append(tp/(tp+fp))
            recall.append(tp/(tp+fn))
            s.append(len(b)*scale)
        plt.plot(recall, precision, alpha=0.8)
        plt.scatter(recall, precision, s=s, alpha=0.25, linewidths=0)
        # plt.gca().invert_xaxis()
        plt.xlabel('Recall')
        plt.ylabel('Precision')
        plt.savefig(prefix + 'Precision-Recall.png', dpi=600)
        plt.close()


        # BWA-MEM plot
        x = []
        y = []
        s=[]
        tp = df_fn['tp'].sum()
        fp = df_fn['fp'].sum()
        for i, b in df_fn.groupby('mapq'):
            if tp+fp == 0:
                continue
            y.append((fp+tp)/n)
            x.append(fp/(tp+fp))
            s.append(len(b)*scale)
            tp -= b['tp'].sum()
            fp -= b['fp'].sum()
        plt.plot(x, y, alpha=0.8)
        plt.scatter(x, y, s=s, alpha=0.25, linewidths=0)
        plt.ylabel('tp+fp/total')
        plt.xlabel('fp/tp+fp')
        plt.savefig(prefix + 'bwamempaper_mapq.png', dpi=600)
        plt.close()


        # bwamem - number of alignments
        x = []
        y = []
        s=[]
        tp = df_fn['tp'].sum()
        fp = df_fn['fp'].sum()
        for i, b in df_fn.groupby('n_target'):
            if tp+fp == 0:
                continue
            y.append((fp+tp)/n)
            x.append(fp/(tp+fp))
            s.append(len(b)*scale)
            tp -= b['tp'].sum()
            fp -= b['fp'].sum()
        plt.plot(x, y, alpha=0.8)
        plt.scatter(x, y, s=s, alpha=0.25, linewidths=0)
        plt.ylabel('tp+fp/total')
        plt.xlabel('fp/tp+fp')
        plt.savefig(prefix + 'expected_alns_bwamem.png', dpi=600)
        plt.close()


        # precision - number of alignments
        x = []
        y = []
        s=[]
        for i, b in df_fn.groupby('n_target'):
            tp = b['tp'].sum()
            fp = b['fp'].sum()
            if tp+fp == 0:
                continue
            y.append(tp/(tp+fp))
            x.append(i)
            s.append(len(b)*scale)

        plt.plot(x, y, alpha=0.8)
        plt.scatter(x, y, s=s, alpha=0.25, linewidths=0)
        plt.ylabel('Precision')
        plt.xlabel('Expected alignments')
        plt.savefig(prefix + 'expected_alns_precision.png', dpi=600)
        plt.close()


def expected_mappings_per_read(prefix, ins_events):
    expect = []
    for i in ins_events.values():
        expect += [j[2] - j[1] for j in i.get_ins_blocks()]
    plt.hist(expect, bins=np.arange(0, 800, 25))
    plt.ylabel('count')
    plt.xlabel('aln size')
    plt.tight_layout()
    plt.savefig(prefix + 'expected_mappings_sizes.png', dpi=600)
    plt.close()

    plt.hist([len(i.get_ins_blocks()) for i in ins_events.values()], bins=range(0, 15))
    plt.ylabel('count')
    plt.xlabel('aln size')
    plt.tight_layout()
    plt.savefig(prefix + 'expected_mappings_per_read.png', dpi=600)
    plt.close()


def find_duplications(ins_events, df_fn, prefix):
    duplication = []
    translocation = []
    deletion = []
    insertion = []
    for idx, qname in ins_events.items():
        e = ins_events[idx]
        target_ins_alns = e.get_ins_blocks()
        for l in range(0, len(target_ins_alns)-1):
            if target_ins_alns[l][0] == target_ins_alns[l+1][0] and abs(target_ins_alns[l+1][1] - target_ins_alns[l][2]) < 50:
                duplication.append(idx)
            if target_ins_alns[l][0] != target_ins_alns[l+1][0]:
                translocation.append(idx)
            if target_ins_alns[l][0] == target_ins_alns[l+1][0] and abs(target_ins_alns[l][2] - target_ins_alns[l+1][1]) < 1000:
                deletion.append(idx)
        if len(target_ins_alns) == 3:
            for l in range(0, len(target_ins_alns) - 2):
                if target_ins_alns[l][0] == target_ins_alns[l+2][0] and abs(target_ins_alns[l][2] - target_ins_alns[l+1][1]) < 1000:
                    insertion.append(idx)
    df_fn['duplication'] = 0
    df_fn['translocation'] = 0
    df_fn['deletion'] = 0
    df_fn['insertion'] = 0
    df_fn.loc[df_fn['qname'].isin(duplication), 'duplication'] = 1
    df_fn.loc[df_fn['qname'].isin(translocation), 'translocation'] = 1
    df_fn.loc[df_fn['qname'].isin(deletion), 'deletion'] = 1
    df_fn.loc[df_fn['qname'].isin(insertion), 'insertion'] = 1

    print('duplications: ', len(duplication))
    print('translocations: ', len(translocation))
    print('deletions: ', len(deletion))
    print('insertions: ', len(insertion))

    df_fn.to_csv(prefix + 'benchmark_res_fn.csv', sep='\t', index=False)


def benchmark_simple(args):
    table = pd.read_csv(args.query, sep='\t')
    table = table.loc[table['is_secondary'] != 1]
    table = table.drop_duplicates()
    table.reset_index(drop=True, inplace=True)

    prefix = args.prefix
    if prefix[-1] != '.':
        prefix += '.'
    prefix = "/".join([args.out, prefix])

    ins_events, n = load_frag_info(args.target)

    print('Expected number of fragments: ', n)
    if args.include_figures:
        expected_mappings_per_read(prefix, ins_events)
        figures = True
    else:
        figures = False

    analyse_ins_numbers(table, ins_events, prefix, n, figures)
    # find_duplications(ins_events, df_fn, prefix)