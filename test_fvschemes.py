import re
content = """
divSchemes
{
    default         none;
    div(phi,U)      bounded Gauss linearUpwind grad(U);
    div(phi,k)      bounded Gauss upwind;
    div(phi,epsilon) bounded Gauss upwind;
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}
"""
content = re.sub(r"div\(phi,U\).*?;", "div(phi,U)      bounded Gauss upwind;", content)
print(content)
