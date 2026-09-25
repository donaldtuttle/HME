# Related work

HME belongs in comparisons of associative memory designs. The following primary literature supplies established operations and evaluation questions; it does not establish equivalence or performance for this implementation.

- **Tony A. Plate (1995), “Holographic Reduced Representations.”** IEEE Transactions on Neural Networks 6(3), 623–641. [Paper](https://www2.fiit.stuba.sk/~kvasnicka/CognitiveScience/6.prednaska/plate.ieee95.pdf), [DOI](https://doi.org/10.1109/72.377968). Describes distributed vector representations with circular-convolution association and approximate retrieval.
- **Kenny Schlegel, Peer Neubert, Peter Protzel (2021), “A comparison of Vector Symbolic Architectures.”** Artificial Intelligence Review. [Accepted manuscript](https://arxiv.org/abs/2001.11797), [DOI](https://doi.org/10.1007/s10462-021-10110-3). Compares eleven VSA designs, bundle capacity, unbinding, and combinations of binding and superposition.

HME shares distributed numeric patterns, superposition, and similarity scoring with this broader literature. Its actual encoding is a normalized 2D FFT outer-product pattern placed in a spatial patch. Its identity ranker also reads retained item vectors and patterns. These differences matter: a standard HRR implementation cannot be claimed merely because both systems use complex numbers or FFTs.

An explicit HRR or frequency-domain VSA implementation is a useful future baseline. Claims of architectural novelty or better recall require comparative measurements under matched information and storage budgets.
