# lanyrd-pyvo-pull
Simple script for pulling information from Lanyrd event and serializing them into YAML

## Usage

```
python pyvo-pull.py "http://lanyrd.com/series/brno-pyvo/"
```

Creates directory `brnenske-pyvo-brug`, which will contain files `2011-04-26-poprve.yaml`, `2011-06-13-druhe.yaml`, etc.

```
python pyvo-pull.py "http://lanyrd.com/2015/brno-pyvo-april/"
```

Creates file `2015-04-30-freelancing.yaml`.

## Requirements

- Python 3
- `requirements.txt`
