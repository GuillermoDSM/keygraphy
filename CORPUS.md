# Corpus

The default `es-LA` practice corpus contains 10,000 words ranked from nine
modern Spanish-language open books. The books were published in 1970 or later
and are distributed under CC BY 4.0. The locale name describes the application
package; the sources represent Spanish across Spain and Latin America.

## Method

The builder is `tools/build_word_corpus.py`. HTML books are crawled within the
declared book path. PDF books are converted with `pdftotext`. Text is normalized
to Unicode NFC, URLs and numeric footnote markers are removed, and tokens are
restricted to Spanish letters, including `áéíóúüñ`. Recurring English
boilerplate and PDF extraction fragments are excluded before ranking.

For each source, a word frequency is calculated as:

```text
count / valid_token_count * 1,000,000
```

The three source frequencies in each genre are averaged first. The final score
is the average of the three genre scores, so no genre dominates because its
books are longer. Words must occur in at least two of the nine sources. The
generated JSON retains `word`, `score`, `rank`, `coverage`, and the original
count from every source.

## Sources

| Genre | Book | Year | License | Record |
| --- | --- | ---: | --- | --- |
| Historia | *Culturas y Civilizaciones de los Países Hispanos* | 2025 | CC BY 4.0 | [Open Textbook Library](https://open.umn.edu/opentextbooks/textbooks/culturas-y-civilizaciones-de-los-paises-hispanos-cultures-and-civilizations-of-the-hispanic-countries?locale=es) |
| Historia | *Historia y su didáctica* | 2025 | CC BY 4.0 | [RISEI](https://editorial.risei.org/index.php/risei/catalog/book/44) |
| Historia | *La Edad Moderna y la Enseñanza Secundaria* | 2024 | CC BY 4.0 | [PEPA](https://pepa.une.es/handle/123456789/79764) |
| Literatura | *Cien años de Platero y yo: 1914-2014* | 2017 | CC BY 4.0 | [PEPA](https://pepa.une.es/entities/publication/9dfe98c9-2976-420d-86ea-52012c3df083) |
| Literatura | *Genio e Ingenio del Poeta Judeo-Andaluz Miguel/Daniel Leví de Barrios* | 2024 | CC BY 4.0 | [PEPA](https://pepa.une.es/entities/publication/03889016-6629-4437-9346-1a8e29dddfec) |
| Literatura | *Poeta y mar* | 2019 | CC BY 4.0 | [PEPA](https://www.pepa.une.es/items/bf793f86-ae7d-4cbc-aad7-dc32ec4d8d53) |
| Negocios | *Introducción a los Negocios* | 2022 | CC BY 4.0 | [LibreTexts Español](https://espanol.libretexts.org/Bookshelves/Negocio/Negocios/Negocio_Introductorio/Libro%3A_Introduccion_a_los_Negocios_%28OpenStax%29) |
| Negocios | *Macroeconomía* | 2022 | CC BY 4.0 | [LibreTexts Español](https://espanol.libretexts.org/Bookshelves/Ciencias_Sociales/Economia/Libro%3A_Macroeconomia_%28OpenStax%29) |
| Negocios | *Introducción a la estadística empresarial* | 2022 | CC BY 4.0 | [OpenStax](https://openstax.org/books/introducci%C3%B3n-estad%C3%ADstica-empresarial/pages/prefacio) |

The exact download URLs and SHA-256 hashes are recorded in
`data/words-es-la.sources.json` and `data/words-es-la.meta.json`. The text and
metadata from each source remain attributable to its original authors and
publisher. Some books contain third-party media with separate terms; those
assets are not included in the generated word list.
