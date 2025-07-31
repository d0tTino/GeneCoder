# Parallel Channel Pipeline

GeneCoder's `genecoder.simulators.pipeline.ChannelPipeline` can execute channel steps concurrently. The pipeline now dispatches each step as a future so the next stage starts as soon as the previous one finishes. This overlapping of work is especially helpful when running several simulators or processing many sequences.

Running on a four-core machine with `parallel=True` often cuts the runtime for CPU-bound pipelines nearly in half. Each completed sequence still increments the `oligos_simulated` counter once, so parallel execution only speeds up how quickly those metrics accumulate.

## Threads

Enable threading with `ChannelConfig`:

```python
from genecoder.simulators.pipeline import ChannelPipeline
from genecoder.channel_config import ChannelConfig

pipeline = ChannelPipeline([...])
cfg = ChannelConfig(parallel=True, workers=4)
result = pipeline.simulate(sequence, config=cfg)
```

Process several sequences in parallel using `parallel_map`:

```python
from genecoder.parallel import parallel_map

sequences = ["ACGT", "TGCA", "GATC"]
cfg = ChannelConfig(parallel=True, workers=4)
results = parallel_map(lambda s: pipeline.simulate(s, config=cfg), sequences, workers=4)
```

Run the same from the CLI:

```bash
genecli channel apply --parallel --threads 4 \
    --input-file in.fasta --output-file out.fasta \
    --simulator channelA --simulator channelB
```

## Processes

Use a process pool to avoid the Global Interpreter Lock:

```python
cfg = ChannelConfig(parallel=True, workers=4, use_process_pool=True)
```

Command line example:

```bash
genecli channel apply --parallel --processes 4 \
    --input-file in.fasta --output-file out.fasta \
    --simulator channelA --simulator channelB
```

## MPI

Distributed execution relies on `mpi4py`. Install it and run the program with `mpiexec`:

```bash
pip install mpi4py
```

```python
cfg = ChannelConfig(parallel=True, workers=4, use_mpi=True)
```

```bash
mpiexec -n 4 python my_script.py
```

A YAML configuration can also enable MPI:

```yaml
pipeline:
  parallel: true
  workers: 4
  use_mpi: true
```

Run it with:

```bash
mpiexec -n 4 genecli channel run config.yml
```

MPI requires an installed MPI implementation (such as MPICH or OpenMPI) in addition to `mpi4py`.

### MPI Example

A ready-to-run configuration at `configs/mpi_demo.yaml` shows two simple channels
with `use_mpi: true`. The demo expects an encoded FASTA at
`encoded/message.fasta`. Generate it from any text file:

```bash
genecli encode --input-files message.txt --output-file encoded/message.fasta
```

Execute the pipeline using:

```bash
mpiexec -n 2 genecli channel run configs/mpi_demo.yaml
```

You can also run a short Python example:

```bash
mpiexec -n 2 python scripts/mpi_example.py
```

The script prints the processed sequence from each MPI rank so you can verify
distributed execution.

### mpiexec Quickstart

Follow these steps to run the demo configuration under MPI.

1. Install an MPI runtime and the `mpi4py` package:

   ```bash
   # MPICH
   sudo apt-get install mpich
   # or OpenMPI
   sudo apt-get install openmpi-bin
   pip install mpi4py
   ```

2. Launch the pipeline with `mpiexec`:

   ```bash
   mpiexec -n 2 genecli channel run configs/mpi_demo.yaml
   ```

   OpenMPI users can instead run:

   ```bash
   mpirun -np 2 genecli channel run configs/mpi_demo.yaml
   ```

