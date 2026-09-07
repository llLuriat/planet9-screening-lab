# ETNO Catalog Validation Report

Status: partial.

The V2 catalog structure is canonical, but the orbital values are carried from the V1 example fixture. They are not externally validated in this repository.

Selection rule from `configs/science/etno_selection.yaml`:

- `a_au >= 150`
- `q_au = a_au * (1 - e) >= 30`
- epoch, frame, and source are required

Known limitation:

- The catalog is suitable for pipeline testing and conservative diagnostics, not final scientific claims.

