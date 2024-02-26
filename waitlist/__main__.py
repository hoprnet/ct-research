import pprint
from os import environ as env

import click
from dotenv import load_dotenv
from dune_client.client import DuneClient
from dune_client.query import QueryBase

from .dune_entry import DuneEntry
from .registration_entry import RegistrationEntry

load_dotenv()
dune = DuneClient.from_env()


def remove_duplicates(
    data: list, attribute: str = "safe_address", keep_last: bool = False
) -> list:
    _data = data[-1::-1] if keep_last else data
    attributes = [getattr(entry, attribute) for entry in _data]

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
    "--waitlist",
    default="network_waitlist.xlsx",
    help="Network waitlist file (.xlsx)",
)
@click.option(
    "--output-file",
    default="final_waitlist.xlsx",
    help="Output file (.xlsx)",
)
def main(nrfile: str, waitlist: str, output_file: str):
    # Loading onboarding waitlist (from Dune)
    onboarding_data = dune.run_query_dataframe(QueryBase(env.get("DUNE_QUERY_ID")))
    onboardings = DuneEntry.fromDataFrame(onboarding_data)
    unique_onboarding = remove_duplicates(onboardings, "node_address", True)
    addresses_from_onboarding = [e.safe_address for e in unique_onboarding]

    # Loading registration data (from Andrius)
    registrations = RegistrationEntry.fromXLSX(nrfile)
    unique_registrations = remove_duplicates(registrations, "node_address", True)

    print(f"Registrations\t\t\t{len(unique_registrations)}")
    pprint(unique_registrations)

    # Loading network waitlist (from Cryptpad)
    # network_waitlist = NetworkWaitlistEntry.fromXLSX(waitlist)
    # eligible_addresses = [e.safe_address for e in network_waitlist if e.eligible]

    # print(f"Eligible addresses\t\t{len(eligible_addresses)}")

    # Cleanup registrations to get only valid candidates
    # waitlist_candidates = [
    #     e for e in unique_registrations if e.safe_address not in eligible_addresses
    # ]
    print(f"Candidates after cleanup\t{len(unique_registrations)}")

    # Filtering candidates by stake and NFT ownership
    waitlist = []
    for c in unique_registrations:
        if c.safe_address not in addresses_from_onboarding:
            print(f"Address not in onboarding: {c.safe_address}")
            continue

        index = addresses_from_onboarding.index(c.safe_address)

        candidate = unique_onboarding[index]
        candidate.node_address = c.node_address

        if candidate.wxHOPR_balance < 10000:
            print(f"Low balance: {candidate.safe_address} ({candidate.wxHOPR_balance})")
            continue

        if candidate.wxHOPR_balance < 30000 and not candidate.nr_nft:
            print(
                f"Low balance (NFT): {candidate.safe_address} ({candidate.wxHOPR_balance})"
            )
            continue

        if not candidate.node_address.startswith("0x"):
            print(
                f"Invalid node address: {candidate.safe_address} ({candidate.node_address})"
            )
            continue

        waitlist.append(candidate)

    nr_waitlist = [e for e in waitlist if e.nr_nft]
    stake_waitlist = [e for e in waitlist if not e.nr_nft]

    print(f"NFT holders in waitlist\t\t{len(nr_waitlist)}")
    print(f"non-NFT holders in waitlist\t{len(stake_waitlist)}")

    # Sorting users according to COMM team rules
    ordered_waitlist = applyCOMMrules(nr_waitlist, stake_waitlist, (20, 10))
    print(f"Final waitlist size\t\t{len(ordered_waitlist)}")

    # Sanity check
    assert len(ordered_waitlist) == len(nr_waitlist) + len(stake_waitlist)
    assert len(ordered_waitlist) == (len(remove_duplicates(ordered_waitlist)))

    # Exporting waitlist
    DuneEntry.toDataFrame(ordered_waitlist).to_excel(output_file, index=False)


if __name__ == "__main__":
    main()
