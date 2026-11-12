/* C fallbacks for the x86 maths.S on non-x86 hosts (macOS arm64). */
#include <math.h>
#include <setjmp.h>
#include <stdlib.h>

#define D(name, expr) double cgc_##name(double x) { return (expr); }
#define F(name, expr) float cgc_##name##f(float x) { return (expr); }
#define L(name, expr) long double cgc_##name##l(long double x) { return (expr); }
#define ALL(name, expr) D(name, expr) F(name, expr) L(name, expr)

ALL(sin, sin(x)) ALL(cos, cos(x)) ALL(tan, tan(x))
ALL(log, log(x)) ALL(log10, log10(x)) ALL(log2, log2(x))
ALL(exp, exp(x)) ALL(exp2, exp2(x)) ALL(sqrt, sqrt(x))
ALL(fabs, fabs(x)) ALL(rint, rint(x))
ALL(remainder, remainder(x, 2.0 * 3.14159265358979323846))
ALL(twopi_rem, remainder(x, 2.0 * 3.14159265358979323846))
double cgc_exp2x(double x) { return exp2(x); }
double cgc_significand(double x) { int e; return frexp(x, &e) * 2.0; }
float cgc_significandf(float x) { int e; return frexpf(x, &e) * 2.0f; }
long double cgc_significandl(long double x) { int e; return frexpl(x, &e) * 2.0L; }

/* These need a second argument; keep the assembly-compatible names. */
double cgc_pow(double x, double y) { return pow(x, y); }
float cgc_powf(float x, float y) { return powf(x, y); }
long double cgc_powl(long double x, long double y) { return powl(x, y); }
double cgc_atan2(double y, double x) { return atan2(y, x); }
float cgc_atan2f(float y, float x) { return atan2f(y, x); }
long double cgc_atan2l(long double y, long double x) { return atan2l(y, x); }
double cgc_scalbn(double x, int n) { return scalbn(x, n); }
float cgc_scalbnf(float x, int n) { return scalbnf(x, n); }
long double cgc_scalbnl(long double x, int n) { return scalbnl(x, n); }
double cgc_scalbln(double x, long n) { return scalbln(x, n); }
float cgc_scalblnf(float x, long n) { return scalblnf(x, n); }
long double cgc_scalblnl(long double x, long n) { return scalblnl(x, n); }

/* Only used by a few challenges; static corpus does not execute them. */
int cgc_setjmp(jmp_buf env) { (void)env; abort(); }
void cgc_longjmp(jmp_buf env, int value) { (void)env; (void)value; abort(); }
