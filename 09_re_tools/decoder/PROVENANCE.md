# Decoder provenance

Preserved, unmodified Python port and opcode tables:
- https://github.com/ayyo42069/c166-disasm-plugin
- snapshot 35d4488ee6b35d246dfc0dc87e0667b385f9d43e
- Author: Kristof (krstoff.com).

Original table-driven Perl decoder:
- https://github.com/hn/c166-dis
- snapshot 31b605362ac55b2710b8c87a29e83ba73b18899b
- Copyright 2000 Hajo Noerenberg; GPL version 3.
- License: https://www.gnu.org/licenses/gpl-3.0.txt

The full upstream snapshots are not bundled in this public edition. Required decoder sources/tables and COPYING are included here; upstream commit identifiers are retained for provenance.
The Python header states its license follows the original GPL-3.0.

Review-specific corrections are in ../review_decode.py, separate from these files.
Known errors in the upstream rendering include bitoff RAM addressing, MOVBZ operands,
immediate EXTP formatting, instruction-range display, and incomplete BFLD masks.
The wrapper validates selected instruction vectors; it is NOT a fully validated C166
processor model and does not track EXTR/ESFR context or arbitrary control flow.
