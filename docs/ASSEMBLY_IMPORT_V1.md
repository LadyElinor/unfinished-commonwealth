# Assembly public docket import

From the research host checkout, install the optional `assembly` extra in a verification environment with the cryptography dependency available. The core workshop and the C2 participant do not require it. Run:

```sh
python -m commonwealth.assembly_v1 examples/assembly_v1/public_record.json --checkpoint examples/assembly_v1/checkpoint.json
```

The importer bounds the input, checks the frozen registry, signatures, nonces and event chain against the required checkpoint, replays the exact Assembly 0.2 rules and separately recounts each closed public chamber roll. It returns references, public assignment metadata and simulated outcomes in a read-only review, with no database, signing functions, execution endpoint, A1 grant or participant capability. The only Assembly source moved into this module is the 0.2 rule interpreter and the separate public recount, with a package-relative import in the latter. The signed sample and checkpoint are copied from the [Warranted Commonwealth Legislative Kit v0.2](https://chatgpt.com/library?file_id=libfile_a0d0602ef210819190dcd0d724d7f6b2&account_id=personal).

The exposed 38-action example contains an amendment to a bill's wording after a jury remand, two ordinary chamber tallies, an executive veto, two override tallies, and a court challenge. It produces `PUBLISHED_IN_SIMULATION` and opposite local count dispositions. This example's checkpoint and record come from the same source. In a real trust exercise, obtain the expected checkpoint from a separately controlled custodian. A signature cannot establish physical voter intent, ballot custody, independent offices or the truth of matching returns. The importer never opens individual ballots. It cannot transform these records into the separate 23-field A1 input or prove a right to govern.

The new [agent participation profile](AGENT_PARTICIPATION_V1.md) uses an operator-supplied checkpoint reference in its workshop role and the source-bound public assignment in its Assembly research role. Its work choices remain defined by the B1.1 host.
