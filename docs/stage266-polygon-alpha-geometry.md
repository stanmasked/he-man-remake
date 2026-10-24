# Stage266 — original collision polygons versus atlas alpha

## Purpose

Stage265 confirmed exact filename matches between three collision-tile references used in Level 1-1 and three original geometry resources. Stage266 decodes these geometry files as polygons, rasterizes each polygon at pixel centers of its corresponding atlas rectangle and compares polygon occupancy with atlas alpha threshold 128.

This is independent cross-format geometry evidence, not proof of which collision response the original iOS game applies.

## Owner-private original IPA measurements

All three linked shapes used in Level 1-1 parsed successfully: one triangle and two four-vertex polygons. They contain finite, nondegenerate vertices and are byte-identical in the medium and xlarge resource packs.

| Sample | Medium polygon-versus-alpha IoU | Xlarge IoU |
| --- | ---: | ---: |
| Named used polygon A | 0.909091 | 0.934018 |
| Named used polygon B | 0.959381 | 0.968750 |
| Named used polygon C | 0.987194 | 0.993265 |

Across all three used named tile IDs:

- Medium pack: 3,072 pixels compared, 48 alpha-versus-polygon mismatches, aggregate IoU **0.969072**.
- Xlarge pack: 12,288 pixels compared, 132 mismatches, aggregate IoU **0.978519**.
- These metrics use a center-point even-odd polygon fill, no smoothing and an alpha threshold of 128/255.
- The polygon geometry stays in a 32-unit local tile domain while xlarge raster sampling applies a 2x pixel scale.

The shape-polygon areas approximate the visual alpha silhouettes. The differences are mostly near polygon boundaries. This supports an authored tile shape relationship. Exact resource names and geometry coordinates remain in the private Stage265 Drive report.

## Source and limits

The Stage266 tool combines Stage265 lexical resource-link checks, the bounded shape parser and the bounded PNG loader. It never extracts original resources. Polygon coordinates and image pixels are held in memory only. The private JSON report records tile indices and overlap counts, not original vertices or alpha arrays.

The comparison does not determine solidity and does not prove that the original engine uses alpha to construct colliders. It does not establish:

- runtime instantiation of the polygon collider;
- tile placement and scale in the physics world;
- slope adhesion, one-way collisions, damage triggers or contact response;
- whether unnamed tiles use rectangular, implicit or different geometry;
- parity between actual iOS gameplay and the Switch prototype.

Do not import alpha images or polygons into Switch physics on this evidence alone.

## Private command

Run from the repository root, using the user-owned IPA held off-repository:

    PYTHONPATH=src python -m heman_tools.collision_polygon_alpha_parity --ipa /secure/private/He-Man-v2.0.0.ipa --map MUMap1-1.map --out local_reports/stage266-level1-polygon-alpha.json

## Public regression coverage

CI creates fictional shape polygon bytes, synthetic collision tilesets and maps, and generated PNGs. Tests cover exact geometry-image matching, divergent alpha pixels, differing geometry source bytes, missing named shapes, differing map bytes and private output redaction. CI never accesses the original IPA.

## Next gate

Validate how these polygons are attached to tile instances in the runtime collision map, and whether physical body creation uses the referenced geometry files. Record actual physical response independently before modifying native Switch gameplay.
