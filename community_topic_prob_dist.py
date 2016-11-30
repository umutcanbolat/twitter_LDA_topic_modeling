import gensim
from gensim import utils, corpora, models
import ast
import re
import os
import sys
import pickle
import numpy as np
import matplotlib.pyplot as plt
from shutil import copyfile
import tweets_on_LDA as tlda
import plot_distances as pltd

def aggregate_tweets(i, clique, tweets_dir):
    print('Aggregating tweets for clique_' + str(i))
    if not os.path.exists('aggregated_tweets/clique_' + str(i)):
        with open('aggregated_tweets/clique_' + str(i), 'w') as outfile:
            for user in ast.literal_eval(clique):
                if os.path.exists(tweets_dir + str(user)):
                    with open(tweets_dir + str(user)) as tweet:
                        for line in tweet:
                            outfile.write(line)

def get_doc_topics(lda, bow):
    gamma, _ = lda.inference([bow])
    topic_dist = gamma[0] / sum(gamma[0])
    return [(topic_id, topic_value) for topic_id, topic_value in enumerate(topic_dist)]

def doc_to_vec(tweet, dictionary, lda):
    doc = tlda.convert_to_doc(tweet)

    # create bag of words from input document
    doc_bow = dictionary.doc2bow(doc)

    # queries the document against the LDA model and associates the data with probabalistic topics
    doc_lda = get_doc_topics(lda, doc_bow)
    return gensim.matutils.sparse2full(doc_lda, lda.num_topics)

def draw_dist_graph(filename, dense_vec):
    if not os.path.exists(filename + '.png'):
        print('Drawing probability distribution graph for ' + filename)
        y_axis = []
        x_axis = []
                        
        for topic_id, dist in enumerate(dense_vec):
            x_axis.append(topic_id + 1)
            y_axis.append(dist)
        width = 1 

        plt.bar(x_axis, y_axis, width, align='center', color='r')
        plt.xlabel('Topics')
        plt.ylabel('Probability')
        plt.title('Topic Distribution for clique')
        plt.xticks(np.arange(2, len(x_axis), 2), rotation='vertical', fontsize=7)
        plt.subplots_adjust(bottom=0.2)
        plt.ylim([0, np.max(y_axis) + .01])
        plt.xlim([0, len(x_axis) + 1])
        plt.savefig(filename)
        plt.close()

def write_topn_words(lda, output_path):
    if not os.path.exists(output_path + 'topn_words.txt'):
        print('Writing topn words for LDA model')
        reg_ex = re.compile('(?<![\s/])/[^\s/]+(?![\S/])')
        with open(output_path + 'topn_words.txt', 'w') as outfile:
            for i in range(lda.num_topics):
                outfile.write('{}\n'.format('Topic #' + str(i + 1) + ': '))
                for word, prob in lda.show_topic(i, topn=20):
                    word = reg_ex.sub('', word)
                    outfile.write('\t{}\n'.format(word.encode('utf-8')))
                outfile.write('\n')

def write_jsd_nums(i, clique_vec, community, dictionary, lda, all_doc_vecs, tweets_dir):
    if not os.path.exists('aggregated_tweets/community_user_distances/jensen_shannon_community_' + str(i)):
        with open('aggregated_tweets/community_user_distances/jensen_shannon_community_' + str(i), 'w') as outfile:
            for user in ast.literal_eval(community):
                if not user in all_doc_vecs:
                    if os.path.exists(tweets_dir + str(user)):
                        print('Writing Jensen Shannon distance for user ' + str(user) + ' in community ' + str(i))
                        jsd = pltd.jensen_shannon_divergence(clique_vec, doc_to_vec(tweets_dir + str(user), dictionary, lda))
                        outfile.write('{}\t{}\t{}\n'.format(user, 'clique', jsd))
                else:
                    print('Writing Jensen Shannon distance for user ' + str(user) + ' in community ' + str(i))
                    jsd = pltd.jensen_shannon_divergence(clique_vec, all_doc_vecs[user])
                    outfile.write('{}\t{}\t{}\n'.format(user, 'clique', jsd))


# clique_top: clique topology, comm_top: community topology, tweets_dir: path of downloaded tweets dir
# dict_loc: dictionary, lda_loc: lda model,
# user_topics_dir: directory where lda model was used in plot_distances to create graphs

# python2.7 community_topic_prob_dist.py cliques communities dnld_tweets/ data/twitter/tweets.dict data/twitter/tweets_100_lda_lem_5_pass.model user_topics_100
def main(clique_top, comm_top, tweets_dir, dict_loc, lda_loc, user_topics_dir):
    # load wiki dictionary
    dictionary = corpora.Dictionary.load(dict_loc)

    # load trained wiki model from file
    lda = models.LdaModel.load(lda_loc)

    if not os.path.exists(os.path.dirname('aggregated_tweets/')):
        os.makedirs(os.path.dirname('aggregated_tweets/'), 0o755)

    if not os.path.exists(os.path.dirname('aggregated_tweets/' + user_topics_dir + 'distribution_graphs/')):
        os.makedirs(os.path.dirname('aggregated_tweets/' + user_topics_dir + 'distribution_graphs/'), 0o755)

    if not os.path.exists(os.path.dirname('aggregated_tweets/' + user_topics_dir + 'community_user_distances/')):
        os.makedirs(os.path.dirname('aggregated_tweets/' + user_topics_dir + 'community_user_distances/'), 0o755)

    write_topn_words(lda, 'aggregated_tweets/' + user_topics_dir)

    with open(clique_top, 'r') as infile:
        for i, clique in enumerate(infile):
            aggregate_tweets(i, clique, tweets_dir)

    if os.path.exists('aggregated_tweets/' + user_topics_dir + 'document_vectors.pickle'):
        with open('aggregated_tweets/' + user_topics_dir + 'document_vectors.pickle') as infile:
            clique_vecs = pickle.load(infile)
    else:
        clique_vecs = {}

    for path, dirs, files in os.walk('aggregated_tweets/'):
        for filename in files:   
            if not filename in clique_vecs:
                print('Getting document vector for ' + filename)
                clique_vecs[filename] = doc_to_vec(path + filename, dictionary, lda)
            draw_dist_graph('aggregated_tweets/' + user_topics_dir + 'distribution_graphs/' + filename, clique_vecs[filename])
        break # stop before traversing into newly created dirs

    with open('aggregated_tweets/' + user_topics_dir + 'document_vectors.pickle', 'wb') as outfile:
        pickle.dump(clique_vecs, outfile)

    with open(user_topics_dir + 'all_community_doc_vecs.pickle', 'rb') as infile:
        all_doc_vecs = pickle.load(infile)

    with open(comm_top, 'r') as infile:
        for i, community in enumerate(infile):
            write_jsd_nums(i, clique_vecs['clique_' + str(i)], community, dictionary, lda, all_doc_vecs, tweets_dir)

if __name__ == '__main__':
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6]))

