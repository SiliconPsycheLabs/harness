"""Rows written one by one. Every row that cost model time touches the disk the moment it arrives (`<out>.partial`,
flushed and synced), a rerun skips the keys already done, a last line cut by a kill is dropped, and `<out>` is
written when the run closes."""
import json
import os


class Vaso:
    def __init__(self, out, chiave=None, rinumera=True, verboso=True):
        self.out, self.parziale, self._key = out, out + ".partial", chiave
        self.righe = []
        seen = set()
        for path in (self.parziale, out):
            if os.path.exists(path):
                for line in open(path, encoding="utf-8"):
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue                    # a line cut by a kill in the middle of a write
                    k = json.dumps(row, sort_keys=True)
                    if k not in seen:
                        seen.add(k)
                        self.righe.append(row)
        self._f = None

    @property
    def chiavi(self):
        return {self._key(r) for r in self.righe} if self._key else set()

    def da_fare(self, lavori, chiave):
        done = self.chiavi
        todo = [j for j in lavori if chiave(j) not in done]
        if done:
            print(f"resume: {len(self.righe)} rows already written, {len(todo)} of {len(lavori)} to do", flush=True)
        return todo

    def __enter__(self):
        self._f = open(self.parziale, "a", encoding="utf-8")
        return self

    def versa(self, riga):
        self.righe.append(riga)
        self._f.write(json.dumps(riga, ensure_ascii=False) + "\n")
        self._f.flush()
        os.fsync(self._f.fileno())

    def __exit__(self, *_):
        self._f.close()
        with open(self.out, "w", encoding="utf-8") as f:
            for r in self.righe:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"{len(self.righe)} rows -> {self.out}", flush=True)
