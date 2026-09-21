# Fuentes

## Corpus de práctica

`data/words-es-literatura.json` contiene las 10.000 palabras más frecuentes
en los libros españoles incluidos en `data/books/`. Se genera de forma
reproducible con `tools/build_word_corpus.py`:

- convierte el texto a minúsculas;
- cuenta las palabras del alfabeto de práctica;
- ordena por frecuencia descendente y, en empate, alfabéticamente;
- conserva las primeras 10.000 palabras.

Los datos de generación están en `data/words-es-literatura.meta.json`.

## Libros españoles incluidos

The books in `data/books/` are Luis Segalá y Estalella's Spanish translations
of Homer's epics, sourced from Project Gutenberg:

- *La Ilíada*, eBook 57654: https://www.gutenberg.org/ebooks/57654
- *La Odisea*, eBook 58221: https://www.gutenberg.org/ebooks/58221

Both source editions are identified by Project Gutenberg as public domain in
the United States. The generated files retain the poem cantos while omitting
Gutenberg notices, front matter, indexes, illustrations, and verse numbers.
Project Gutenberg's trademark and license terms apply to use of its name and
source files: https://www.gutenberg.org/policy/license.html
