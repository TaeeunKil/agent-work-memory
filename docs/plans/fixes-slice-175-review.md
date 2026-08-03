# Slice 175 review fixes

## Review outcome

The footer move kept the existing action bindings intact and the sibling-based
Graph rule removed the utility landmark from layout and accessibility output.

## Finding and fix

1. **Fix - mobile Graph retained one navigation bar of extra scroll.** The
   desktop `.main` minimum height remained `100vh` below the 58px mobile rail,
   so the graph ended 58px below the viewport even though its own height was
   correct. The mobile main area now uses `calc(100svh - 58px)`. Browser
   verification confirmed a 58px rail plus 786px graph exactly fills an 844px
   viewport with no document overflow.

## Final review

No findings. Desktop verification showed the ordinary-view footer pinned to
the viewport bottom and Graph using the full 720px canvas with the footer set
to `display: none`.
