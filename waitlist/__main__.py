import asyncio
import os
from datetime import datetime

import click
from dotenv import load_dotenv
from dune_client.client import DuneClient
from dune_client.query import QueryBase

from .dune_entry import DuneEntry
from .graphql_providers import ProviderError, SafesProvider
from .registration_entry import RegistrationEntry
from .subgraph_entry import SubgraphEntry

load_dotenv()
dune = DuneClient.from_env()

import logging

logging.getLogger('gql.transport.aiohttp').setLevel(logging.CRITICAL)

def remove_duplicates(
    data: list, param_list: list[str] = ["safe_address"], keep_last: bool = False
) -> list:
    _data = data[-1::-1] if keep_last else data
    attributes = []

    for entry in _data:
        attributes.append("-".join(getattr(entry, param) for param in param_list))
    
    duplicates_free = []
    for attribute in set(attributes):
        index = attributes.index(attribute)

        duplicates_free.append(_data[index])

    return duplicates_free


def applyCOMMrules(nr_waitlist: list, stake_waitlist: list, chunk_sizes: tuple):
    nr_chunk_size, stake_chunk_size = chunk_sizes
    nr_index, stake_index = 0, 0

    ordered_waitlist = []

    nr_waitlist.sort(key=lambda x: x.date)
    stake_waitlist.sort(key=lambda x: x.date)

    while len(ordered_waitlist) != (len(nr_waitlist) + len(stake_waitlist)):
        if nr_index < len(nr_waitlist):
            ordered_waitlist.extend(nr_waitlist[nr_index : nr_index + nr_chunk_size])
            nr_index += nr_chunk_size

        if stake_index < len(stake_waitlist):
            ordered_waitlist.extend(
                stake_waitlist[stake_index : stake_index + stake_chunk_size]
            )
            stake_index += stake_chunk_size

    return ordered_waitlist


@click.command()
@click.option(
    "--nrfile",
    default="network_register.xlsx",
    help="Network register file (.xlsx)",
)
@click.option(
    "--output-file",
    default="final_waitlist.xlsx",
    help="Output file (.xlsx)",
)
def main(nrfile: str, output_file: str):
    # Loading onboarding waitlist (from Dune)
    dune_query = QueryBase(os.environ.get("DUNE_QUERY_ID"))
    onboarding_data = dune.run_query_dataframe(dune_query)
        
    dune_data = DuneEntry.fromDataFrame(onboarding_data)
    dune_unique = remove_duplicates(dune_data, ["safe_address"], True)
    unique_dune_safe_addresses = [e.safe_address for e in dune_unique]


    provider = SafesProvider(os.environ.get("SUBGRAPH_SAFES_BALANCE_URL_BACKUP"))
    deployed_safes = list[SubgraphEntry]()
    try:
        for safe in asyncio.run(provider.get()):
            entries = [
                SubgraphEntry.fromSubgraphResult(safe["registeredNodesInNetworkRegistry"])
            ]
            deployed_safes.extend(entries)

    except ProviderError as err:
        print(f"get_registered_nodes: {err}")
    deployed_safes_addresses = [s.safe_address for s in deployed_safes]
    running_nodes = sum([s.nodes for s in deployed_safes], [])

    print("\033[1m", end="")
    print(f"SubgraphEntry // Loaded {len(deployed_safes_addresses)} entries", end="")
    print("\033[0m") # requires refactoring
    
    # Loading registration data (from Andrius)
    registrations = RegistrationEntry.fromXLSX(nrfile)
    unique_registrations = remove_duplicates(registrations, ["safe_address","node_address"], True)

    waitlist_candidates = unique_registrations
    print(f"Candidates after cleanup\t{len(waitlist_candidates)}")

    # Filtering candidates by stake and NFT ownership
    waitlist = []
    for c in waitlist_candidates:
        if c.safe_address in unique_dune_safe_addresses:
            index = unique_dune_safe_addresses.index(c.safe_address)
            candidate = dune_unique[index]
            candidate.node_address = c.node_address

        elif c.safe_address in deployed_safes_addresses:
            index = deployed_safes_addresses.index(c.safe_address)
            deployed_safe = deployed_safes[index]
            candidate = DuneEntry(
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                deployed_safe.safe_address, 
                "", 
                deployed_safe.wxHoprBalance, 
                False,
                None,
            )
            candidate.node_address = c.node_address
            
        else:
            continue

        if candidate.wxHOPR_balance < 10000:
            continue

        if candidate.wxHOPR_balance < 30000 and not candidate.nr_nft:
            continue

        if not candidate.node_address.startswith("0x"):
            continue

        if candidate.node_address in running_nodes:
            continue

        waitlist.append(candidate)

    nr_waitlist = [e for e in waitlist if e.nr_nft]
    stake_waitlist = [e for e in waitlist if not e.nr_nft]

    print(f"NFT holders in waitlist\t\t{len(nr_waitlist)}")
    print(f"non-NFT holders in waitlist\t{len(stake_waitlist)}")

    # Sorting users according to COMM team rules
    ordered_waitlist = applyCOMMrules(nr_waitlist, stake_waitlist, (20, 10))
    print(f"Final waitlist size\t\t{len(ordered_waitlist)}")

    # Exporting waitlist
    DuneEntry.toDataFrame(ordered_waitlist).to_excel(output_file, index=False)

    # Sanity check
    assert len(ordered_waitlist) == len(nr_waitlist) + len(stake_waitlist)
    assert len(ordered_waitlist) == (len(remove_duplicates(ordered_waitlist, ["safe_address", "node_address"])))

if __name__ == "__main__":
    main()
