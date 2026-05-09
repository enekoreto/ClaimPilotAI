import hashlib
import re
from pathlib import Path

from app.config import get_settings
from app.models.claims import ClaimType, PolicyClause


CLAUSE_RE = re.compile(r"^(?P<id>[A-Z]+-\d+): (?P<title>.+)$")


class PolicyRetriever:
    def __init__(self, policy_dir: Path | str = "data/policies"):
        self.policy_dir = Path(policy_dir)
        self._clauses = self._load_clauses()
        self._chroma_collection = None
        if get_settings().vector_store == "chroma":
            self._chroma_collection = self._build_chroma_collection()

    def retrieve(self, claim_type: ClaimType, query: str, top_k: int = 4) -> list[PolicyClause]:
        if self._chroma_collection is not None:
            return self._retrieve_chroma(claim_type, query, top_k)
        query_terms = self._terms(query)
        candidates = [c for c in self._clauses if c.policy_type == claim_type]
        scored: list[PolicyClause] = []
        for clause in candidates:
            clause_terms = self._terms(f"{clause.title} {clause.text}")
            overlap = len(query_terms & clause_terms)
            score = min(1.0, 0.35 + overlap / max(len(query_terms), 1))
            scored.append(clause.model_copy(update={"score": round(score, 3)}))
        return sorted(scored, key=lambda c: c.score, reverse=True)[:top_k]

    def _load_clauses(self) -> list[PolicyClause]:
        clauses: list[PolicyClause] = []
        for path in sorted(self.policy_dir.glob("*.md")):
            policy_type = ClaimType(path.stem.replace("_policy", ""))
            current_id = ""
            current_title = ""
            buffer: list[str] = []
            for line in path.read_text(encoding="utf-8").splitlines():
                match = CLAUSE_RE.match(line.strip())
                if match:
                    if current_id:
                        clauses.append(
                            PolicyClause(
                                policy_type=policy_type,
                                clause_id=current_id,
                                title=current_title,
                                text=" ".join(buffer).strip(),
                                score=0,
                            )
                        )
                    current_id = match.group("id")
                    current_title = match.group("title")
                    buffer = []
                elif current_id and line.strip():
                    buffer.append(line.strip())
            if current_id:
                clauses.append(
                    PolicyClause(
                        policy_type=policy_type,
                        clause_id=current_id,
                        title=current_title,
                        text=" ".join(buffer).strip(),
                        score=0,
                    )
                )
        return clauses

    @staticmethod
    def _terms(text: str) -> set[str]:
        stop = {"the", "and", "for", "with", "from", "that", "this", "claim", "after"}
        return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2 and t not in stop}

    def _build_chroma_collection(self):
        try:
            import chromadb
        except ImportError as exc:
            raise RuntimeError("VECTOR_STORE=chroma requires the chromadb package.") from exc

        client = chromadb.Client()
        collection = client.get_or_create_collection(
            "claimpilot_policy_clauses", embedding_function=HashEmbeddingFunction()
        )
        if collection.count() == 0:
            collection.add(
                ids=[c.clause_id for c in self._clauses],
                documents=[f"{c.title}. {c.text}" for c in self._clauses],
                metadatas=[
                    {
                        "policy_type": c.policy_type.value,
                        "clause_id": c.clause_id,
                        "title": c.title,
                        "text": c.text,
                    }
                    for c in self._clauses
                ],
            )
        return collection

    def _retrieve_chroma(self, claim_type: ClaimType, query: str, top_k: int) -> list[PolicyClause]:
        result = self._chroma_collection.query(
            query_texts=[query],
            n_results=max(top_k * 2, top_k),
            where={"policy_type": claim_type.value},
        )
        clauses = []
        for metadata, distance in zip(result["metadatas"][0], result["distances"][0], strict=False):
            score = max(0.0, min(1.0, 1.0 - float(distance)))
            clauses.append(
                PolicyClause(
                    policy_type=ClaimType(metadata["policy_type"]),
                    clause_id=metadata["clause_id"],
                    title=metadata["title"],
                    text=metadata["text"],
                    score=round(score, 3),
                )
            )
        return clauses[:top_k]


class HashEmbeddingFunction:
    def __call__(self, input: list[str]) -> list[list[float]]:
        vectors = []
        for text in input:
            buckets = [0.0] * 64
            for term in PolicyRetriever._terms(text):
                digest = hashlib.sha256(term.encode("utf-8")).hexdigest()
                buckets[int(digest[:8], 16) % len(buckets)] += 1.0
            norm = sum(v * v for v in buckets) ** 0.5 or 1.0
            vectors.append([v / norm for v in buckets])
        return vectors
