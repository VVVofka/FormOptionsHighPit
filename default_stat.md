# Default Statistics Configuration

Documentation for parameters in `default_stat.json`.

## General

| Parameter | Value | Description |
|-----------|-------|-------------|
| AppLeft | "100" | Window left position (pixels) |
| AppTop | "100" | Window top position (pixels) |
| AppWidth | "800" | Window width (pixels) |
| AppHeight | "600" | Window height (pixels) |

## Gener (General Generation Parameters)

| Parameter | Value | Description |
|-----------|-------|-------------|
| FieldSize | "128" | Size of the field/grid |
| PointsMode | "Count" | Point generation mode: `Count` (fixed number) or `Density` |
| PointsSame | "True" | Whether all point types have same count |
| PointsTotal | "1000" | Total number of points to generate |
| PointsR | "300" | Red points count (when PointsSame=False) |
| PointsG | "300" | Green points count |
| PointsB | "400" | Blue points count |
| Distrib | "Uniform" | **Distribution type**: `Uniform`, `Normal`, `Areas`, `Custom` |
| DistribCommon | "True" | Use common distribution for all colors |
| NormalX | "0" | Normal distribution X mean |
| NormalY | "0" | Normal distribution Y mean |
| NormalSX | "10" | Normal distribution X standard deviation |
| NormalSY | "10" | Normal distribution Y standard deviation |
| Areas | "0,0,10,10" | Area rectangles for Areas distribution (x,y,w,h per area) |
| Weights | "1.0 1.0 1.0 1.0 1.0 1.0" | Weights for custom distribution (6 values) |

### Distrib Values
- **Uniform** - Random uniform distribution across field
- **Normal** - Gaussian/normal distribution (uses NormalX, NormalY, NormalSX, NormalSY)
- **Areas** - Points concentrated in defined rectangular areas (uses Areas parameter)
- **Custom** - Weighted custom distribution (uses Weights parameter)

## ProcUp (Processing Up)

| Parameter | Value | Description |
|-----------|-------|-------------|
| Table | "0000002102030130002100012020110002032020020030030130110030030030002100012020110000010000000010002020000020000000110010000000000002032020020030032020000020000000020020000000000030030000000030000130110030030030110010000000000030030000000030000030000030000000" | Processing table as string of digits (0-3) |

## ProcDn (Processing Down)

| Parameter | Value | Description |
|-----------|-------|-------------|
| TableF | "0.0 0.05 0.1 0.2 0.33 0.5 0.71 1.0" | Float processing table values (space-separated) |
| UseTemplates | "True" | Whether to use templates for processing |