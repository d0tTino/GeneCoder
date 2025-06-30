# Glossary

This page defines key terms used throughout the GeneCoder documentation.

### Using Glossary Tooltips

The GUI and helix viewer highlight glossary terms at runtime. Hovering a term
shows its short definition and clicking opens an overlay with the full text.
This behaviour is provided by a small JavaScript helper that loads
`glossary.json`. Call `applyGlossary()` after rendering HTML to enable it.

## GC content
The percentage of guanine (G) and cytosine (C) bases in a DNA sequence. Balanced GC content (often around 40–60%) improves stability and processability.

## Homopolymer
A run of identical nucleotides, e.g. `AAAAA`. Long homopolymers can cause synthesis and sequencing errors.

## Forward Error Correction (FEC)
Techniques that add redundancy to encoded data so errors can be detected and corrected during decoding.
