# ROA Collector

This program downloads the validated RPKI ROAs from RIPE NCC's validator site and output to compressed JSON files.

## Install

```shell
python3 setup install --user
```

## Usage

There are two subcommands:
- `roa-collector now`: download the most recent ROA lists from the API endpoint at https://rpki-validator.ripe.net/api/export.json. There is no parameters for this subcommand.
- `roa-collector hist`: download historical ROAs from the RIPE's FTP site at "https://ftp.ripe.net/rpki/". There are two parameters to allow narrowing down the search time range to a year or a month:
  - `--year Y`: only download ROAs for `Y` year
  - `--month M`: only download ROAs for `M` month (needs to specify `--year` as well)

**Required parameter**:
- `-d` (`--dir`): specify the directory to which the data should be downloaded to

## Data Storage

The historical data (daily) is downloaded to: 
- `ROOT_DATA_DIR/YEAR/MONTH/DAY/roas.daily.UNIX_TIMESTAMP.json.gz`

The current data (every 5 minutes) is downloaded to: 
- `ROOT_DATA_DIR/YEAR/MONTH/DAY/HOUR/roas.5min.UNIX_TIMESTAMP.json.gz`

## Data Format

The historical data and real-time data share the same JSON format:
```json
{
  "roas": [
    {
      "asn": "AS37674",
      "prefix": "41.191.212.0/22",
      "maxLength": 24,
      "ta": "AfriNIC RPKI Root"
    },
    {
      "asn": "AS37674",
      "prefix": "41.242.144.0/21",
      "maxLength": 24,
      "ta": "AfriNIC RPKI Root"
    },
    ...
  ]
}
```