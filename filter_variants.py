#! /usr/bin/env python

import os
import os.path
import datetime
import argparse
import csv
import logging

import colorlog

import ConfigParser

logger = colorlog.getLogger()
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
handler.setFormatter(
    colorlog.ColoredFormatter('%(log_color)s%(levelname)s:%(name)s:%(message)s'))
logger.addHandler(handler)


def get_thresholds(filters):
    # get filter values
    thresholds = dict()
    config = ConfigParser.SafeConfigParser()
    config.read(filters)

    # default quality filters for DNA
    thresholds['DNA_t_cov'] = float(config.get('quality_filters', 'DNA_t_cov'))
    thresholds['DNA_t_altC'] = float(config.get('quality_filters', 'DNA_t_altC'))
    thresholds['DNA_t_af'] = float(config.get('quality_filters', 'DNA_t_af'))

    # default quality filters for RNA
    thresholds['RNA_t_cov'] = float(config.get('quality_filters', 'RNA_t_cov'))
    thresholds['RNA_t_altC'] = float(config.get('quality_filters', 'RNA_t_altC'))
    thresholds['RNA_t_af'] = float(config.get('quality_filters', 'RNA_t_af'))

    # default thresholds for misalignment at exon junctions
    thresholds['RNA_t_percent'] = float(config.get(
        'quality_filters', 'RNA_t_altref_total_percent'))
    thresholds['DNA_t_percent'] = float(config.get(
        'quality_filters', 'DNA_t_altref_total_percent'))

    # default somatic filters
    thresholds['DNA_n_af'] = float(config.get('somatic_filters','DNA_n_af'))
    thresholds['DNA_n_altC'] = float(config.get('somatic_filters', 'DNA_n_altC'))
    thresholds['RNA_n_af'] = float(config.get('somatic_filters', 'RNA_n_af'))
    thresholds['RNA_n_altC'] = float(config.get('somatic_filters', 'RNA_n_altC'))
    return thresholds


def assign_numeric_type(line):
    for key in line.keys():
        if is_float(line[key]):
            line[key] = "{:.2f}".format(float(line[key]))
        elif(line[key].isdigit()):
            line[key] = int(line[key])
    return line


def somatic_filtering(variant_summary, thresholds, somatic_summary):
    with open (somatic_summary,  'wb') as fh1:
        writer = csv.writer(fh1, delimiter='\t')
        with open(variant_summary, 'r') as fh2:
            records = csv.DictReader(fh2,  delimiter='\t')
            headers = records.fieldnames
            writer.writerow(headers)
            for line in records:
                assign_numeric_type(line)
                content = [line[i] for i in headers]
                if pass_somatic_filters(thresholds, line):
                    writer.writerow(content)


def pass_somatic_filters(thresholds, line):
    if line['in_strelka'] == 'in_strelka':
        return True
    else:
        if line['t_DNA_cov'] == 'na':
            # Only transcriptome is sequenced for this tumor! 
            if (line['n_RNA_AF'] <= thresholds['RNA_n_af'] or
                line['n_RNA_AltC'] <= thresholds['RNA_n_altC']):
                return True
        elif line['t_RNA_cov'] == 'na':
            # Only genome is sequenced for this tumor! 
            if (line['n_DNA_AF'] <= thresholds['DNA_n_af'] or
                line['n_DNA_AltC'] <= thresholds['DNA_n_altC']):
                return True
        else:
            # Both genome and transcriptome are sequenced for this tumor! 
            if ((line['n_RNA_AF'] <= thresholds['RNA_n_af'] or
                line['n_RNA_AltC'] <= thresholds['RNA_n_altC']) and
                (line['n_DNA_AF'] <= thresholds['DNA_n_af'] or
                line['n_DNA_AltC'] <= thresholds['DNA_n_altC'])):
                return True

            
def quality_filtering(variant_summary, thresholds, filtered_summary):
    with open(filtered_summary,  'wb') as fh:
        writer = csv.writer(fh, delimiter='\t')
        with open(variant_summary, 'r') as handle:
            records = csv.DictReader(handle,  delimiter='\t')
            headers = records.fieldnames
            writer.writerow(headers)
            for line in records:
                assign_numeric_type(line)
                content = [line[i] for i in headers]
                if  pass_quality_filters(thresholds, line):
                    writer.writerow(content)


def pass_quality_filters(thresholds, line):
    # pass_quality = False
    RNA_t_altref_total = line["t_RNA_RefC"] + line["t_RNA_AltC"]
    DNA_t_altref_total = line["t_DNA_RefC"] + line["t_DNA_AltC"]
    if line['in_strelka'] == 'in_strelka':
        return True
    else:
        if line['t_DNA_cov'] == 'na':
            # Only transcriptome is sequenced for this tumor! 
            if (line['t_RNA_cov'] >= thresholds['RNA_t_cov'] and
                line['t_RNA_AltC'] >= thresholds['RNA_t_altC'] and
                line['t_RNA_AF'] >= thresholds['RNA_t_af'] and
                RNA_t_altref_total >= thresholds['RNA_t_percent']*line['t_RNA_cov']):
                return True
        elif line['t_RNA_cov'] == 'na':
            # Only genome is sequenced for this tumor! 
            if (line['t_DNA_cov'] >= thresholds['DNA_t_cov'] and
                line['t_DNA_AltC'] >= thresholds['DNA_t_altC'] and
                line['t_DNA_AF'] >= thresholds['DNA_t_af'] and
                DNA_t_altref_total >= thresholds['DNA_t_percent']*line['t_DNA_cov']):
                return True
        else:
            # Both genome and transcriptome are sequenced for this tumor! 
            if (line['t_DNA_cov'] >= thresholds['DNA_t_cov'] and
                line['t_DNA_AltC'] >= thresholds['DNA_t_altC'] and
                line['t_DNA_AF'] >= thresholds['DNA_t_af'] and
                DNA_t_altref_total >= thresholds['DNA_t_percent']*line['t_DNA_cov']):
                return True
            elif (line['t_RNA_cov'] >= thresholds['RNA_t_cov'] and
                line['t_RNA_AltC'] >= thresholds['RNA_t_altC'] and
                line['t_RNA_AF'] >= thresholds['RNA_t_af'] and
                RNA_t_altref_total >= thresholds['RNA_t_percent']*line['t_RNA_cov']):
                return True

            
def is_float(s):
    if not s.isdigit():
        try:
            float(s)
            return True
        except ValueError:
            return False


def make_occurrence_dict(infile):
    gene_patients = {}
    var_patients = {}
    gene_variants = {}
    with open (infile) as fh:
        records = csv.DictReader(fh,  delimiter='\t')
        for line in records:
            gene = line['gene']
            chr = line["chromosome"]
            pos = line["position"]
            ref = line["ref_base"]
            alt = line["alt_base"]
            patient = line["patient_ID"].split('_')[0]
            variant = '_'.join([gene, chr, pos, ref, alt])
            try:
                gene_patients[gene].append(patient)
            except KeyError:
                gene_patients[gene] = [patient]
            try:
                var_patients[variant].append(patient)
            except KeyError:
                var_patients[variant] = [patient]
            try:
                gene_variants[gene].append(variant)
            except KeyError:
                gene_variants[gene] = [variant]
    # remove duplicate items
    for gene in gene_patients:
        gene_patients[gene] = len(list(set(gene_patients[gene])))  
    #print gene_patients
    for variant in var_patients:
        var_patients[variant] = len(list(set(var_patients[variant])))
    #pprint(var_patients)
    for gene in gene_variants:
        gene_variants[gene] = len(list(set(gene_variants[gene])))
    #print gene_variants
    return [gene_patients, var_patients, gene_variants]


def calculate_occurrence(infile, gene_patients, var_patients, gene_variants):
    outfile = infile.replace('.tmp', '.txt')
    with open (outfile,  'wb') as fh:
        writer = csv.writer( fh, delimiter='\t')
        with open (infile, 'r') as handle:
            records = csv.DictReader(handle,  delimiter='\t')
            headers = records.fieldnames
            new_headers = ([headers[0]] +
                           ['filtered_num_patients_gene_level',
                            'filtered_num_SNVs_gene_level'] +
                           headers[1:7] +
                           ['filtered_num_patients_SNV_level'] +
                           headers[7:])
            writer.writerow(new_headers)
            for line in records:
                variant = '_'.join([line['gene'],
                                    line['chromosome'],
                                    line['position'],
                                    line['ref_base'],
                                    line['alt_base']])
                num_gene_patients = gene_patients[line['gene']]
                num_var_patients = var_patients[variant]
                num_gene_variants = gene_variants[line['gene']]
                content = [line[i] for i in headers]
                final_content = ([content[0]] +
                                 [num_gene_patients,
                                  num_gene_variants] +
                                 content[1:7] +
                                 [num_var_patients] +
                                 content[7:])
                writer.writerow(final_content)
                                   
def parse_args():
    parser = argparse.ArgumentParser(
        description='Filter variants based on qulaity and somatic filters')
    parser.add_argument(
        '-i', '--input_file',
        help='specify input file', required=True)
    parser.add_argument(
        '-f', '--quality_somatic_filters',
        help='specify quality and somatic filters', required=True)
    parser.add_argument(
        '-p', '--pairing', required=True,
        help='specify if sample paired with matched normal: '
              'paired or unpaired')
    args = parser.parse_args()
    return args


def main():
    logger.info("Quality and somatic filtering script starts at: %s\n" % datetime.datetime.now())
    args = parse_args()

    filtered_summary = '{0}.filtered.tmp'.format(
        os.path.splitext(args.input_file)[0])
    somatic_summary = '{0}.somatic.tmp'.format(
        os.path.splitext(filtered_summary)[0])

    thresholds = get_thresholds(args.quality_somatic_filters)
    quality_filtering(args.input_file, thresholds, filtered_summary)
    if args.pairing == 'unpaired':
        pass
    elif args.pairing == 'paired': 
        somatic_filtering(filtered_summary, thresholds, somatic_summary)

    # recalculate occurrence for filtered summary
    out = make_occurrence_dict(filtered_summary)

    (gene_patients_occur,
     var_patients_occur,
     gene_variants_occur) = out

    calculate_occurrence(filtered_summary,
                         gene_patients_occur,
                         var_patients_occur,
                         gene_variants_occur)

    # recalculate occurrence for somatic summary
    if (os.path.isfile(somatic_summary)):
        out = make_occurrence_dict(somatic_summary)
        
        (gene_patients_occur,
         var_patients_occur,
         gene_variants_occur) = out
        calculate_occurrence(somatic_summary,
                             gene_patients_occur,
                             var_patients_occur,
                             gene_variants_occur)
        os.remove(somatic_summary)

    # remove intermediate files
    # os.remove(filtered_summary)


if __name__ == '__main__':
    main()
