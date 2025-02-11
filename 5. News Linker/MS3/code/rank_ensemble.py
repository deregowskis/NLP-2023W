import os
import json
from collections import defaultdict
import math
from nltk.corpus import stopwords
import numpy as np
import argparse
from utils import *


def rank_ensemble(args, topk=20):
    # directory of a dataset (ex. sta/)
    dataset_dir = f'datasets/{args.dataset}'
    # directory of a current test document (ex. sta/topic_0/)
    topic_dir = f'datasets/{args.dataset}/topics/{args.topic}' # = dataset_dir
    # learned seed-guided text embeddings of the input corpus
    word2emb = load_cate_emb(os.path.join(topic_dir, f'emb_{args.topic}_w.txt'))
    # PLM-based (SloBERTa-based) representations of the most popular slovenian words
    word2bert = load_bert_emb(os.path.join(dataset_dir, f'{args.dataset}_sloberta'))

    # load topic-indicative terms selected after context ensembling
    caseolap_results = []
    with open(os.path.join(topic_dir, f'intermediate_2.txt')) as fin:
        for line in fin:
            data = line.strip()
            #_, res = data.split(':')
            data = data.split(':')
            _, res = data[0], "".join(data[1:])
            caseolap_results.append(res.split(','))
            
    # load the terms together with the corresponding scores and the related documents
    with open(os.path.join(topic_dir, f'intermediate_2_doc_ids.json'), 'r') as fin:
        caseolap_dict = json.load(fin)
       
    # load the seeds
    cur_seeds = []
    with open(os.path.join(topic_dir, f'{args.topic}_seeds.txt')) as fin:
        for line in fin:
            data = line.strip().split(' ')
            cur_seeds.append(data)


    final_dict = {}
    with open(os.path.join(topic_dir, f'{args.topic}_seeds.txt'), 'w') as fout:
        for idx, comb in enumerate(zip(cur_seeds, caseolap_results)):
            seeds, caseolap_res = comb
            # dictionary for calculating the Mean Residual Rank
            word2mrr = defaultdict(float)

            # add ranking based on scores from seed-guided text embeddings
            word2cate_score = {word:np.mean([np.dot(word2emb[word], word2emb[s]) for s in seeds]) for word in word2emb}
            r = 1.
            for w in sorted(word2cate_score.keys(), key=lambda x: word2cate_score[x], reverse=True)[:topk]:
                if w not in word2bert: continue
                word2mrr[w] += 1./r
                r += 1
                 
            # add ranking based on scores from SloBERTA representations
            word2bert_score = {word:np.mean([np.dot(word2bert[word], word2bert[s]) for s in seeds]) for word in word2bert}
            r = 1.
            for w in sorted(word2bert_score.keys(), key=lambda x: word2bert_score[x], reverse=True)[:topk]:
                if w not in word2emb: continue
                word2mrr[w] += 1./r
                r += 1
            
            # add ranking based on scores form all contexts ensemble
            r = 1.
            for w in caseolap_res[:topk]:
                word2mrr[w] += 1./r
                r += 1

            # sort the terms based on their ranks  
            score_sorted = sorted(word2mrr.items(), key=lambda x: x[1], reverse=True)
            # select top-k terms
            top_terms = [x[0].replace(' ', '') for x in score_sorted if x[1] > args.rank_ens and x[0] != '']
            top_mrr = [x[1] for x in score_sorted if x[1] > args.rank_ens and x[0] != '']
            # save the terms
            fout.write(' '.join(top_terms).replace(":","") + '\n')

            # get a list seed-related documents
            cur_dict = caseolap_dict[seeds[0]]
            terms_docs_dict = dict()
            # for each of the top-term save its mrr, similarity score and ids of the related documents
            for term, mrr in zip(top_terms,top_mrr):
                docs_ids = [] if not term in cur_dict else cur_dict[term]
                terms_docs_dict[term] = {
                    'mrr': mrr, 
                    'similarity_score': docs_ids['similarity_score'] if len(docs_ids) > 0 else None,
                    'doc_ids': docs_ids['doc_ids'] if len(docs_ids) > 0 else []
                }
            final_dict[seeds[0]] = terms_docs_dict
            
        print(f'Saved ranked terms to {topic_dir}/{args.topic}_seeds.txt')

    with open(os.path.join(topic_dir,f'{args.topic}_seeds_doc_ids.json'), 'w') as fout2:
        json.dump(final_dict,fout2)
        print(f'Saved document ids featuring ranked terms to {topic_dir}/{args.topic}_seeds_doc_ids.json')

if __name__ == '__main__':
    
    parser = argparse.ArgumentParser(description='main', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--dataset', default='nyt', type=str)
    parser.add_argument('--topic', default='topic', type=str)
    parser.add_argument('--topk', default=20, type=int)
    parser.add_argument('--rank_ens', default=0.3, type=float)
    args = parser.parse_args()

    rank_ensemble(args, args.topk)