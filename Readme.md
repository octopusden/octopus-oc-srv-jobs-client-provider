## Client Provider microservice

### Environment variables.

#### Required

    - *PSQL\_URL*
    - *PSQL\_USER*
    - *PSQL\_PASSWORD*

#### Optional
    - *DJANGO\_TIMEZONE* default: **Etc/UTC**
    - *COUNTERPARTY\_ENABLED* default: **False**
    - *COUNTERPARTY\_PATH* default: `client_counterparties.yml` in current working directory

## Client counterparty functionality

Gives a some abstract value for each customer code specified as the argument. May be used for customer grouping.
This option may be deprcated soon.
Counterparties are listed in *YAML*-file provided separately.
