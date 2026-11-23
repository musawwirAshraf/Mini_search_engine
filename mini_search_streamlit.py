import io, re, math, html
import streamlit as st
from pypdf import PdfReader

st.set_page_config(page_title="Mini Search Engine", page_icon="🔎")
STOPWORDS = {"the", "a", "an", "is", "are", "of", "to", "in", "and", "or", "for", "on", "it", "this", "that"}
TOP_N = 10


@st.cache_data(show_spinner="File padh rahe hain...")
def get_pages(name, data):
    if name.lower().endswith(".pdf"):
        return [p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages]
    return [data.decode("utf-8", errors="ignore")]


def make_notes(name, pages, by_paragraph):
    """Har page (ya paragraph) ek 'note' banta hai."""
    notes = []
    for page_no, text in enumerate(pages, start=1):
        for chunk in (re.split(r"\n\s*\n", text) if by_paragraph else [text]):
            chunk = re.sub(r"\s+", " ", chunk).strip()
            if chunk:
                notes.append({"file": name, "page": page_no, "text": chunk})
    return notes


def tokenize(text):
    return [w for w in re.findall(r"\w+", text.lower()) if w not in STOPWORDS]


def build_index(notes):
    """index: word -> set(note ids) | tf: note id -> {word: count}"""
    index, tf = {}, {}
    for note_id, note in enumerate(notes):
        tf[note_id] = {}
        for word in tokenize(note["text"]):
            tf[note_id][word] = tf[note_id].get(word, 0) + 1
            index.setdefault(word, set()).add(note_id)
    return index, tf


def search(query, index, tf, total, mode):
    words = tokenize(query)
    if not words:
        return [], words
    sets = [index.get(w, set()) for w in words]
    matched = set.intersection(*sets) if mode == "AND" else set.union(*sets)
    results = []
    for note_id in matched:
        score = sum(tf[note_id][w] * (math.log((total + 1) / (len(index[w]) + 1)) + 1)
                    for w in words if w in tf[note_id])
        results.append((note_id, score))
    return sorted(results, key=lambda x: x[1], reverse=True), words


def show(text, words, width=350):
    """Match ke aas-paas ka hissa, match <mark> se highlight."""
    pattern = re.compile(r"\b(" + "|".join(map(re.escape, words)) + r")\b", re.IGNORECASE)
    if len(text) > width:
        m = pattern.search(text)
        start = max(0, (m.start() if m else 0) - width // 3)
        text = ("... " if start else "") + text[start:start + width] + (" ..." if start + width < len(text) else "")
    return pattern.sub(r"<mark>\1</mark>", html.escape(text))


# ---------- UI ----------
st.title("🔎 Mini Search Engine")
st.caption("Inverted index (dictionary + set) + TF-IDF: Google ka core idea.")

files = st.file_uploader("📂 PDF ya TXT upload karo", type=["pdf", "txt"], accept_multiple_files=True)
if not files:
    st.info("Shuru karne ke liye ek ya zyada file upload karo.")
    st.stop()

c1, c2 = st.columns(2)
by_paragraph = c1.radio("Search unit", ["Page", "Paragraph"]) == "Paragraph"
mode = c2.radio("Mode", ["OR", "AND"], help="OR: koi bhi word. AND: saare words.")

notes = [n for f in files for n in make_notes(f.name, get_pages(f.name, f.getvalue()), by_paragraph)]
if not notes:
    st.warning("Koi text nahi mila (PDF scanned/image ho sakti hai).")
    st.stop()
index, tf = build_index(notes)
st.write(f"✅ **{len(files)}** file(s) | **{len(notes)}** notes | **{len(index)}** unique words")

# Form nahi: phone par text box se bahar tap karte hi (ya Enter se) query seedha mil jati hai
query = st.text_input("🔍 Keyword search karo", placeholder="e.g. patent registration").strip()
st.button("Search 🔎")   # tap karne se text box commit hota hai aur results aa jate hain
if not query:
    st.caption("Word likho aur Enter dabao (ya Search tap karo).")

if query:
    results, words = search(query, index, tf, len(notes), mode)
    if not results:
        st.warning("❌ Koi result nahi mila.")
    else:
        st.subheader(f"{len(results)} result(s) for \"{query}\"")
        for rank, (note_id, score) in enumerate(results[:TOP_N], 1):
            n = notes[note_id]
            st.markdown(f"**#{rank}** · 📄 {n['file']} · page {n['page']} · relevance `{score:.2f}`")
            st.progress(score / results[0][1])
            st.markdown(show(n["text"], words), unsafe_allow_html=True)
            with st.expander("Poora text"):
                st.markdown(show(n["text"], words, width=10**9), unsafe_allow_html=True)
            st.divider()

with st.expander("🧠 Inverted index dekho"):
    word = st.text_input("Koi word likho", key="idx").strip().lower()
    if word:
        st.write("Is word wale notes:", sorted(i + 1 for i in index.get(word, [])) or "koi nahi")
        