# Third-party graphics runtime

Source: https://github.com/pineapple-pager-projects/pineapple_pager_pagerctl

Pinned commit: 30ef1028500ba1d0303d24ea5d62497407bac77d

Upstream author: brAinphreAk. The upstream README declares MIT licensing.

Included unchanged: lib/pagerctl.py, lib/libpagerctl.so, vendor/pagerctl/src/*, vendor/pagerctl/UPSTREAM_README.md. The stb headers carry their own embedded notices and licenses.

Bundled libpagerctl.so SHA-256: f0f5d3213c77e360fa4cf912c5a122d2dd1b39713ae2cdf7c6ba6dc7ead5e4e5

ELF: 32-bit, little-endian, MIPS shared object; dynamic dependencies include libc.so and libgcc_s.so.1. Runtime compatibility must be confirmed on the actual Pager firmware. This is a compiled upstream artifact; a local rebuild was not performed. See project tools/build_pagerctl.py for rebuilding from the included source.

## MIT License notice

Copyright (c) brAinphreAk and pagerctl contributors

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
