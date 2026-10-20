# Limitations

Read this before citing output from Christos in a paper or acting on it in a
laboratory.

## 1. Enumeration is not prediction of feasibility

The engine enumerates transformations whose structural pattern matches a
template.  A listed entry means *this template applies to this substructure*.
It does not mean the reaction proceeds, gives the major product, or gives any
isolable yield under the stated conditions.  There is no kinetic or
thermodynamic model of rate in the public build; the optional xTB layer supplies
ΔG estimates only, and only when it is installed.

## 2. Conditions are evidence classes, not protocols

Condition annotations record the class of conditions under which a template was
observed upstream (for example "aqueous, heated").  They are not validated
recipes and do not carry concentrations, times or work-up detail.  Treat them
as pointers to the source record.

## 3. Coverage is bounded by the template library

Reactions outside the library are not reported, and absence of a prediction is
not evidence of absence.  The library was mined from a finite set of upstream
reaction records; its coverage of any particular natural-product scaffold is
unknown and should be measured, not assumed.

## 4. Input resolution depends on the data tables

Herb, formula and species resolution depends on external tables that are not
distributed here.  Resolution failures, alias ambiguity and processing-method
distinctions are properties of those tables, not of the reaction engine.

## 5. No ranking, no scoring

Output entries are not ordered by confidence and carry no composite score.
This is intentional: the project has no validated ground truth that would
justify a ranking.  Any consumer who adds one is adding their own model.

## 6. Not a synthesis planner

The public build cannot plan a synthesis towards an arbitrary target, cannot
accept free-form reagents, and cannot look up purchasable building blocks.  It
is not a substitute for a retrosynthesis planning tool and must not be used as
one.

## 7. Beta status

`v0.9.0-beta`.  The command-line and JSON output formats may change between
releases without a deprecation cycle.
