# Querying the Abstract Content Graph

The Q3062 pilot is not only a translation table. It produces a typed,
traversable Wikibase graph:

```text
Q3062
  └─ abstract paragraph (P21)
       ├─ constructor function
       └─ abstract sentences (inverse P21, qualified by sequence ordinal)
            └─ monolingual content values
```

Existing local properties are reused:

- `P8`: instance of;
- `P21`: part of.

Three properties must be created once in the local Wikibase and entered in
`pilots/Q3062-hero-bindings.csv`:

| Binding token | Datatype | Purpose |
| --- | --- | --- |
| `MONOLINGUAL_CONTENT_PROPERTY` | Monolingual text | Language realization of a sentence |
| `CONSTRUCTOR_FUNCTION_PROPERTY` | Wikibase item | Function constructing a content item |
| `SEQUENCE_ORDINAL_PROPERTY` | String | Ordered position, used as a qualifier |

Property IDs are not guessed because an incorrect datatype cannot be repaired
by changing a QuickStatement. The three class items—abstract function,
abstract paragraph, and abstract sentence—are created by the initial pilot
QuickStatements.

After importing those items and creating the properties:

```bash
python src/main/abstract/prepare_q3062_hero.py prepare
# Fill Q3062-hero-bindings.csv with returned QIDs and property IDs.
python src/main/abstract/prepare_q3062_hero.py check-bindings
python src/main/abstract/prepare_q3062_hero.py write-structure
```

Import `Q3062-hero-structure.quickstatements` to add types, membership,
constructor, ordered composition, and monolingual values.

## Example SPARQL shapes

Replace the three property placeholders with their local IDs.

Retrieve every ordered sentence of the Q3062 hero paragraph:

```sparql
SELECT ?paragraph ?sentence ?ordinal WHERE {
  ?paragraph wdt:P21 wd:Q3062 ;
             wdt:P8 wd:Q_ABSTRACT_PARAGRAPH_CLASS .
  ?sentence p:P21 ?membership .
  ?membership ps:P21 ?paragraph ;
              pq:P_SEQUENCE_ORDINAL ?ordinal .
}
ORDER BY xsd:integer(?ordinal)
```

Retrieve the constructor and French realization:

```sparql
SELECT ?paragraph ?function ?text WHERE {
  ?paragraph wdt:P_CONSTRUCTOR_FUNCTION ?function .
  ?sentence wdt:P21 ?paragraph ;
            wdt:P_MONOLINGUAL_CONTENT ?text .
  FILTER(LANG(?text) = "fr")
}
```

Find every paragraph that reuses a sentence:

```sparql
SELECT ?sentence (COUNT(?paragraph) AS ?uses) WHERE {
  ?sentence wdt:P21 ?paragraph .
  ?paragraph wdt:P8 wd:Q_ABSTRACT_PARAGRAPH_CLASS .
}
GROUP BY ?sentence
HAVING(COUNT(?paragraph) > 1)
```
