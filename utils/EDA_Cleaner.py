import re
import string
import nltk
from typing import List

nltk.download('punkt', quiet=True)
nltk.download('stopwords', quiet=True)

class TextCleaner:
    def __init__(self):
        self.stop_words = set(nltk.corpus.stopwords.words('french') + nltk.corpus.stopwords.words('english'))
        self.punctuation = set(string.punctuation)
        self.tokenizer = nltk.tokenize.word_tokenize

    def to_lowercase(self, text: str) -> str:
        return text.lower()

    def remove_punctuation(self, text: str) -> str:
        return ''.join(char for char in text if char not in self.punctuation)

    def remove_numbers(self, text: str) -> str:
        return re.sub(r'\d+', '', text)

    def remove_stopwords(self, text: str) -> str:
        tokens = self.tokenizer(text)
        return ' '.join(token for token in tokens if token not in self.stop_words)

    def remove_special_chars(self, text: str) -> str:
        return re.sub(r'[^a-zA-Z\s]', '', text)

    def tokenize(self, text: str) -> List[str]:
        return self.tokenizer(text)

class TextPipeline:
    def __init__(self, cleaner: TextCleaner):
        self.cleaner = cleaner

    def process(self, text: str) -> str:
        try:
            text = self.cleaner.to_lowercase(text)
            text = self.cleaner.remove_punctuation(text)
            text = self.cleaner.remove_numbers(text)
            text = self.cleaner.remove_stopwords(text)
            return text.strip()
        except Exception as e:
            raise Exception(f"Erreur dans le pipeline de nettoyage : {str(e)}")