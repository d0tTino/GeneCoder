# Development Roadmap

1. **Foundation (Complete)** – command line interface, multiple encoders, error handling and a basic GUI with asynchronous operations.
2. **Phase 2: Robust Encoding Pipeline**
   - Introduce additional error correction codes such as Reed–Solomon and LDPC.
   - Implement streaming support for handling large files efficiently.
   - Refine GC-content balancing algorithms for more stable synthesis results.
3. **Phase 3: Simulation & Analysis**
   - Model sequencing errors in greater detail to mimic real-world conditions.
   - Provide named sequencing profiles (e.g., `miseq`, `hiseq`, `minion`,
     `promethion`) selectable via CLI options.
   - Integrate with common bioinformatics tools for downstream analysis.
   - Provide automated reports summarizing encoding accuracy and efficiency.
4. **Phase 4: Ecosystem & Automation**
   - Publish a plugin repository enabling community codecs and FEC modules.
   - Require digital signatures for plugins submitted to the new marketplace.
   - Offer workflow templates powered by n8n for routine processing tasks.
   - Package the toolkit for easy container deployment in research pipelines.
5. **Long-Term Vision**
   - Interactive dashboards to visualize storage simulations over time.
   - Cloud-friendly architecture for scaling large simulation batches.
   - Continued collaboration with the research community to expand features.
6. **Documentation Updates**
   - Inline comments in `encoders.py` and `flet_app.py` now point to sections of the Development Vision PDF (Sections III and IV) for added context.
