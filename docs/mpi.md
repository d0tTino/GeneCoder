# MPI Pipeline Execution

GeneCoder can distribute channel pipelines across multiple machines using [MPI](https://en.wikipedia.org/wiki/Message_Passing_Interface). This requires the `mpi4py` package and an installed MPI runtime such as MPICH or OpenMPI. MPI support is optional; local and offline runs work without it.

## Quickstart

1. Install an MPI implementation and `mpi4py`:

```bash
# MPICH
sudo apt-get install mpich
# or OpenMPI
sudo apt-get install openmpi-bin
pip install mpi4py
```

2. Enable MPI in your pipeline configuration by setting `pipeline.use_mpi: true` and choosing the number of workers. The sample configuration [`configs/mpi_demo.yaml`](../configs/mpi_demo.yaml) demonstrates this:

```yaml
pipeline:
  parallel: true
  workers: 2
  use_mpi: true
```

3. Execute the pipeline with `mpiexec`:

```bash
mpiexec -n 2 genecli channel run configs/mpi_demo.yaml
```

Setting `use_mpi: true` automatically selects the MPI executor. The number of workers should match the `-n` argument to `mpiexec`.

## Multi-node Example

To run the same configuration across several machines create a simple host file listing each node and how many processes it should launch:

```text
nodeA slots=2
nodeB slots=2
```

Copy `configs/mpi_demo.yaml` to every node and start the pipeline with:

```bash
mpiexec -hostfile hosts -n 4 genecli channel run configs/mpi_demo.yaml
```

All nodes must have GeneCoder, `mpi4py` and an MPI runtime (MPICH or OpenMPI) installed. MPI support is entirely optional—for local and offline use the pipeline can instead rely on threads or processes as described in [parallel execution](parallel.md).
