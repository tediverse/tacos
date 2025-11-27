import logging
import re
from typing import Optional

from llama_index.core import Document
from llama_index.core.node_parser import SemanticSplitterNodeParser
from llama_index.embeddings.openai import OpenAIEmbedding
from sqlalchemy.orm import Session

from app.models.doc import Doc
from app.services.content_enhancer import ContentEnhancer
from app.services.posts_service import parse_post_data
from app.services.text_embedder import embed_text
from app.settings import settings

logger = logging.getLogger(__name__)


_EMOJI_RANGES = (
    (0x1F1E6, 0x1F1FF),  # flags
    (0x1F300, 0x1F5FF),  # symbols & pictographs
    (0x1F600, 0x1F64F),  # emoticons
    (0x1F680, 0x1F6FF),  # transport & map
    (0x1F700, 0x1F77F),  # alchemical
    (0x1F780, 0x1F7FF),  # geometric ext
    (0x1F800, 0x1F8FF),  # arrows ext
    (0x1F900, 0x1F9FF),  # supplemental symbols
    (0x1FA00, 0x1FA6F),  # chess + more
    (0x1FA70, 0x1FAFF),  # pictographs ext
    (0x1FB00, 0x1FBFF),  # symbols for legacy computing
    (0x1F3FB, 0x1F3FF),  # skin tone modifiers
    (0x2600, 0x26FF),  # misc symbols (includes gender signs)
    (0x2700, 0x27BF),  # dingbats
    (0xFE00, 0xFE0F),  # variation selectors
)


def _is_emoji_char(ch: str) -> bool:
    cp = ord(ch)
    if cp == 0x200D:  # zero width joiner
        return True
    return any(start <= cp <= end for start, end in _EMOJI_RANGES)


def normalize_heading(text: str) -> str:
    """Strip emoji-like glyphs and collapse whitespace for cleaner embeddings."""

    cleaned = "".join(ch for ch in text if not _is_emoji_char(ch))
    collapsed = " ".join(cleaned.split())
    return collapsed.strip()


def extract_sections(text: str):
    """Return markdown headings with their level and start index."""

    pattern = r"^(#{1,6})\s+(.*)$"
    sections = []
    offset = 0

    for line in text.splitlines(keepends=True):
        match = re.match(pattern, line)
        if match:
            level = len(match.group(1))
            raw_title = match.group(2).strip()
            title = normalize_heading(raw_title) or raw_title
            sections.append((level, title, offset))
        offset += len(line)

    return sections


def map_chunks_to_sections(content: str, chunks: list[str], sections):
    """Attach nearest heading info to each chunk using character offsets."""

    chunk_sections = {}
    chunk_heading_paths = {}

    for i, chunk in enumerate(chunks):
        snippet = chunk[:50]
        pos = content.find(snippet)
        if pos == -1:
            pos = 0

        stack = []
        for level, heading, start in sections:
            if start <= pos:
                while stack and stack[-1][0] >= level:
                    stack.pop()
                stack.append((level, heading))
            else:
                break

        chunk_sections[i] = stack[-1][1] if stack else None
        chunk_heading_paths[i] = [h for _, h in stack]

    return chunk_sections, chunk_heading_paths


def ingest_doc(
    db: Session,
    raw_doc: dict,
    *,
    parser,
    enhance_content=ContentEnhancer().enhance_content,
    embed_text_fn=embed_text,
    parse_post_data_fn=None,
    chunk_text_fn=None,
) -> Optional[str]:
    """Ingest a single CouchDB doc into Postgres with chunking + embedding."""

    parse_post_data_fn = parse_post_data_fn or parse_post_data
    chunk_text_fn = chunk_text_fn or chunk_text

    # Parse via post_service (includes frontmatter handling)
    slug = raw_doc.get("path") or raw_doc["_id"]
    post_data = parse_post_data_fn(raw_doc, slug, include_content=True, parser=parser)
    if not post_data or not post_data.get("content"):
        logger.warning(f"Skipped doc {slug} (no content after parsing)")
        return None

    content = post_data["content"]
    title = post_data.get("title", slug)
    slug = post_data.get("slug")

    # Chunk + embed
    chunks = chunk_text_fn(content)
    sections = extract_sections(content)
    chunk_sections, chunk_heading_paths = map_chunks_to_sections(
        content, chunks, sections
    )
    new_docs = []
    success_count = 0

    for i, chunk in enumerate(chunks):
        try:
            # Enhance content with metadata before embedding
            enhanced_content = enhance_content(
                content=chunk,
                title=title,
                metadata={
                    "tags": post_data.get("tags", []),
                    "summary": post_data.get("summary"),
                },
            )
            embedding = embed_text_fn(enhanced_content)
            new_docs.append(
                Doc(
                    document_id=raw_doc["_id"],
                    slug=slug,
                    title=title,
                    content=chunk,  # Store original content for display
                    embedding=embedding,
                    doc_metadata={
                        "order": i,
                        "section": chunk_sections.get(i),
                        "heading_path": chunk_heading_paths.get(i, []),
                        "tags": post_data.get("tags", []),
                        "created_at": post_data.get("publishedAt"),
                        "updated_at": post_data.get("updatedAt"),
                        "summary": post_data.get("summary"),
                        "source": (
                            "blog" if slug.startswith(settings.BLOG_PREFIX) else "kb"
                        ),
                    },
                )
            )
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to embed chunk for doc {slug}: {e}")
            continue

    if success_count > 0:
        # only delete old chunks if we have at least one successful embedding
        db.query(Doc).filter(Doc.document_id == raw_doc["_id"]).delete(
            synchronize_session=False
        )
        db.add_all(new_docs)
        db.commit()
        logger.info(f"Ingested {slug}: {success_count}/{len(chunks)} chunks")
        return slug
    else:
        logger.warning(f"Doc {slug} had no successfully embedded chunks")
        return None


def ingest_all(db: Session, *, parser, ingest_fn=None):
    """One-time ingestion of all CouchDB docs. Also removes deleted docs."""
    ingest_fn = ingest_fn or ingest_doc
    all_docs = [row.get("doc", row) for row in parser.db.all(include_docs=True)]
    for doc in all_docs:
        # Remove deleted docs from Postgres
        if doc.get("deleted", False):
            db.query(Doc).filter(Doc.document_id == doc["_id"]).delete()
            db.commit()
            continue

        # Only ingest "plain" types, meaning markdown files
        if doc.get("type") != "plain":
            continue

        # Only ingest docs under specific paths
        path = doc.get("path", "")
        if not (
            path.startswith(settings.BLOG_PREFIX) or path.startswith(settings.KB_PREFIX)
        ):
            continue

        ingest_fn(db, doc, parser=parser)


def chunk_text(
    text: str,
    *,
    embed_model=None,
) -> list[str]:
    """
    Chunk text for embedding using LlamaIndex semantic splitter.
    Keeping the surface area small: supply a custom embed_model in tests to avoid network calls.
    """
    if not text:
        return []

    embed_model = embed_model or OpenAIEmbedding(
        model="text-embedding-3-small",
        api_key=settings.OPENAI_API_KEY or None,
    )

    splitter = SemanticSplitterNodeParser(embed_model=embed_model)
    nodes = splitter.get_nodes_from_documents([Document(text=text)])
    return [node.get_content() for node in nodes if node.get_content().strip()]
