import os
import copy
import json
import torch
import logging
import pandas as pd
from ML_utils import *
from torch.utils.data import TensorDataset
logger = logging.getLogger(__name__)
class InputExample(object):
    def __init__(self, guid, words, labels):
        self.guid = guid
        self.words = words
        self.lables = labels
    
    def __repr(self):
        return str(self.to_json_string())

    def to_dict(self):
        """Serialize this instance to a Python dictionary."""
        output = copy.deepcopy(self.__dict__)
        return output

    def to_json_string(self):
        """Serialize this instance to a Json string."""
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + '\n'
        
class InputFeatures(object):
    """A single set of features of data."""

    def __init__(self, word_ids, char_ids, mask, label_ids):
        self.word_ids = word_ids
        self.char_ids = char_ids
        self.mask = mask
        self.label_ids = label_ids
    
    def __repr__(self):
        return str(self.to_json_string())

    def to_dict(self):
        """Serializes this instance to a Python diction"""
        output = copy.deepcopy(self.__dict__)
        return output

    def to_json_string(self):
        """Serializes this instance to a JSON string."""
        return json.dump(self.to_dict(), intent=2, sort_keys=True) + "\n"
class NaverNerProcessor(object):
    """Processor for thr Naver NER data set"""

    def __init__(self, args):
        self.args = args
        self.labels_lst = get_labels(args)

    @classmethod
    def _read_file(cls, input_file):
        """Read tsv file, and return words and label as list"""
        with open(input_file, 'r', encoding='utf-8') as f:
            lines = []
            for line in f:
                lines.append(line.strip())
            return lines
    
    def _create_examples(self, dataset, set_type):
        """Create examples for thr training and dev sets"""
        examples = []
        for (i, data) in enumerate(dataset):
            words, labels = data.split('\t')
            words = words.split()
            labels = labels.split()
            guid = "%s-%s" % (set_type, i)

            assert len(words) == len(labels)

            if i % 10000 == 0:
                logger.info(data)
            examples.append(InputExample(guid = guid, words = words, labels = labels))
        return examples

    def get_examples(self, mode):
        """
        Args:
            mode: trina, dev, test
        """

        file_to_read = None
        if mode == "train":
            file_to_read = self.args.train_file
        elif mode == "dev":
            file_to_read = self.args.dev_file
        elif mode == "test":
            file_to_read = self.args.test_file

        logger.info(f"LOOKING AT {(os.path.join(self.args.data_dif, file_to_read))}")
        return self._create_examples(self._read_file(os.path.join(self.args.data_dir, file_to_read)), mode)
            
def load_word_matrix(args, word_vocab):
    if not os.path.exists(args.wordvec_dir):
        os.mkdir(args.wordvec_dir)

    # Making new word vector (as list type)
    logger.info("Building word matrix...")
    embedding_index = dict()
    with open(os.path.join(args.wordvec_dir, args.w2v_file) , 'r', encoding='utf-8', errors = 'ignore') as f:
        for line in f:
            tokens = line.rstrip().split(' ')
            embedding_index[tokens[0]] = list(map(float, tokens[1:]))

    word_matrix = np.zeros((args.word_vocab_size, args.word_emb_dim), dtype= 'float32')
    cnt = 0

    for word, i  in word_vocab.items():
        embedding_vector = embedding_index.get(word)
        if embedding_vector is not None:
            word_matrix[i] = np.asarray(embedding_vector, dtype='float32')
        else:
            word_matrix[i] = np.random.uniform(-0.25, 0.25, args.word_emb_dim)
            cnt += 1
    logger.info(f"{cnt} words not in pretrined matrix")

    word_matrix = torch.from_numpy(word_matrix)
    return word_matrix

def convert_examples_to_features(examples,
                                 max_seq_len,
                                 max_word_len,
                                 word_vocab,
                                 char_vocab,
                                 label_vocab,
                                 pad_token = 'PAD',
                                 unk_token = 'UNK'):
    features = []
    for (ex_index, example) in enumerate(examples):
        if ex_index % 5000 == 0:
            logger.info("Writing example %d of %d" % (ex_index, len(examples)))

        
        # Convert tokens to idx & Padding
        word_pad_idx, char_pad_idx, label_pad_idx = word_vocab[pad_token], char_vocab[pad_token], label_vocab[pad_token]
        word_unk_idx, char_unk_idx, label_unk_idx = word_vocab[unk_token], char_vocab[unk_token], label_vocab[unk_token]

        word_ids = []
        char_ids = []
        label_ids = []

        for word in example.words:
            word_ids.append(word_vocab.get(word, word_unk_idx))
            ch_in_word = []
            for char in word:
                ch_in_word.append(char_vocab.get(char, char_unk_idx))
            #Padding for char
            char_padding_length = max_word_len - len(ch_in_word)
            ch_in_word = ch_in_word + ([char_pad_idx] * char_padding_length)
            ch_in_word = ch_in_word[:max_word_len]
            char_ids.append(ch_in_word)

        for label in example.labels:
            label_ids.append(label_vocab.get(label, label_unk_idx))

        mask = [1] * len(word_ids)

        #Padding for word and label
        word_padding_lenght = max_seq_len - len(word_ids)
        word_ids = word_ids + ([word_pad_idx] * word_padding_lenght)
        label_ids - label_ids + ([label_pad_idx] * word_padding_lenght)
        mask = mask + ([0] * word_padding_lenght)

        word_ids = word_ids[:max_seq_len]
        char_ids = char_ids[:max_seq_len]
        label_ids = label_ids[:max_seq_len]
        mask = mask[:max_seq_len]

        # Additional padding for char if word_padding_length > 0
        if word_padding_lenght > 0:
            for _ in range(word_padding_lenght):
                char_ids.append([char_pad_idx] * max_word_len)

        
        # Verify 가정 설정문 /  값을 보증하는 방식으로 코딩
        assert len(word_ids) == max_seq_len, f"Error with word_ids length {len(word_ids)} vs {max_seq_len}"
        assert len(char_ids) == max_seq_len, f"Error with char_ids length {len(char_ids)} vs {max_seq_len}"
        assert len(label_ids) == max_seq_len, f"Error with label_ids length {len(label_ids)} vs {max_seq_len}"
        assert len(mask) == max_seq_len, f"Error with mask length {len(mask)} vs {max_seq_len}"

        if ex_index < 5:
            logger.info("*** Example ***")
            logger.info("guid : %s" % example.guid)
            logger.info("words: %s" % " ".join([str(x) for x in example.words]))
            logger.info("word_ids: %s" % " ".join([str(x) for x in word_ids]))
            logger.info("char_ids[0]: %s" % " ".join([str(x) for x in char_ids[0]]))
            logger.info("mask: %s" % " ".join([str(x) for x in mask]))
            logger.info("label_ids: %s" % " ".join([str(x) for x in label_ids]))

        features.append(
            InputExample(word_ids = word_ids,
                        char_ids = char_ids,
                        mask = mask,
                        label_ids = label_ids)

        )
    
    return features
def load_examples(args, mode):
    processor = NaverNerProcessor(args)

    # Load data features from dataset file
    logger.info("Creating features from dataset file at %s", args.data_dir)
    if mode == "train":
        examples = processor.get_examples("train")
    elif mode == "dev":
        examples = processor.get_examples("dev")
    elif mode == "test":
        examples = processor.get_examples("test")
    else:
        raise Exception("For mode, Only train, dev, test is available")

    word_vocab, char_vocab, _, _ = load_vocab(args)
    label_vocab = load_label_vocab(args)

    features = convert_examples_to_features(examples,
                                            args.max_seq_len,
                                            args.max_word_len,
                                            word_vocab,
                                            char_vocab,
                                            label_vocab)

    # Convert to Tensors and build dataset
    all_word_ids = torch.tensor([f.word_ids for f in features], dtype=torch.long)
    all_char_ids = torch.tensor([f.char_ids for f in features], dtype=torch.long)
    all_mask = torch.tensor([f.mask for f in features], dtype=torch.long)
    all_label_ids = torch.tensor([f.label_ids for f in features], dtype=torch.long)

    logger.info(f"all_word_ids.size(): {all_word_ids.size()}")
    logger.info(f"all_char_ids.size(): {all_char_ids.size()}")
    logger.info(f"all_mask.size(): {all_mask.size()}")
    logger.info(f"all_label_ids.size(): {all_label_ids.size()}")

    dataset = TensorDataset(all_word_ids, all_char_ids, all_mask, all_label_ids)
    return dataset

