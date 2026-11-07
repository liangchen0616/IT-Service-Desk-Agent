"""In-memory BM25 with Latin words and Chinese character/bigram tokens."""
from collections import Counter
from copy import deepcopy
from math import log, isfinite
import re
from retrieval.contracts import RetrievedChunk, chunk_id, positive_int


def tokenize(text):
    tokens = []
    for part in re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", text.lower()):
        if "\u4e00" <= part[0] <= "\u9fff":
            tokens.extend(part)
            tokens.extend(part[i:i+2] for i in range(len(part)-1))
        else:
            tokens.append(part)
    return tokens


class BM25Retriever:
    def __init__(self, chunks, k1=1.5, b=0.75):
        if not isfinite(k1) or k1 <= 0 or not isfinite(b) or not 0 <= b <= 1:
            raise ValueError("Invalid BM25 parameters")
        self.k1, self.b = k1, b
        self.chunks = list({chunk_id(c): deepcopy(c) for c in chunks}.values())
        self.counts = [Counter(tokenize(c.content)) for c in self.chunks]
        self.lengths = [sum(c.values()) for c in self.counts]
        self.average = sum(self.lengths) / max(1, len(self.lengths))
        self.df = Counter(t for c in self.counts for t in c)

    def retrieve(self, query, top_k=3):
        positive_int(top_k, "top_k")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be nonempty text")
        terms = set(tokenize(query))
        results = []
        for chunk, counts, length in zip(self.chunks, self.counts, self.lengths):
            score = 0.0
            for term in terms:
                tf = counts[term]
                if not tf:
                    continue
                idf = log(1 + (len(self.chunks)-self.df[term]+0.5)/(self.df[term]+0.5))
                score += idf * tf * (self.k1+1) / (tf+self.k1*(1-self.b+self.b*length/self.average))
            if score > 0:
                results.append(RetrievedChunk(deepcopy(chunk), score, "bm25"))
        return sorted(results, key=lambda r: -r.score)[:top_k]
