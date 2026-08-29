# reference/english

Public-domain English prose used as training text by `lib.fitness`, chosen for register: aphoristic wisdom prose, the closest public-domain match to the solved Liber Primus plaintext. Not Cicada material (that is `corpus/`) and not derived analysis (that is `research/`).

| file | work | source |
| --- | --- | --- |
| `meditations-long.txt` | Marcus Aurelius, *Meditations*, trans. George Long | Project Gutenberg #2680 |
| `tao-teh-king-legge.txt` | *The Tao Teh King*, trans. James Legge | Project Gutenberg #216 |
| `emerson-essays-first.txt` | Ralph Waldo Emerson, *Essays — First Series* | Project Gutenberg #2944 |

Retrieved 2026-08-21 from `https://www.gutenberg.org/cache/epub/<id>/pg<id>.txt` with the Project Gutenberg header and footer stripped (the text between the `*** START ... ***` and `*** END ... ***` markers). All three are US public domain.

Editing anything here changes every fitness score and breaks comparability with previously logged experiment scores; the exact training-set size is pinned in `tests/test_stats_fitness.py`. If the training set is deliberately changed, update that pin, say so in the commit, and treat older logged scores as a different scale.
