# viesco

Patches for VSCodium for removing all telemetry and privacy-invasing functionality altogether.

## Quick start
```console
$ python viesco.py
usage: viesco [-h] [-o OUTPUT] [-d] install patch [patch ...]

An utility for configuring VSCodium before first run.

positional arguments:
  install              installation/extraction path of VSCodium
  patch                patch files to apply

options:
  -h, --help           show this help message and exit
  -o, --output OUTPUT  write the automatic script to OUTPUT (.bat)
  -d, --dry-run        perform a run without making any changes
```
- To apply patches: `python viesco.py <install> <patch...>`
- To create an automatic **Batch script**: `python viesco.py -o script.bat <install> <patch...>`
    - To avoid making changes to the current system use `-d` / `--dry-run`


## Contributing
Everyone is welcome to make contributions to the repository. However, please make sure that you comply with the rules below.

**Can be submitted**:
- *Paths to files/folders*, *replace rules* or *configuration* for VSCodium
- *Anything* for removing/breaking/disabling connections to 3rd-party services

**Disallowed pull/feature requests:**
- Disabling open-vsx.org support
- Breaking expected network functionality (e.g. previews of remote images in Markdown)
