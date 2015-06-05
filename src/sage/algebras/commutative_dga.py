"""
Commutative Differential Graded Algebras

An algebra is said to be *graded commutative* if it is endowed with a
grading and its multiplication satisfies the Koszul sign convention:
`yx = (-1)^{ij} xy` if `x` and `y` are homogeneous of degrees `i` and
`j`, respectively. Thus the multiplication is anticommutative for odd
degree elements, commutative otherwise. *Commutative differential
graded algebras* are graded commutative algebras endowed with a graded
differential of degree 1. These algebras can be graded over the
integers or they can be multi-graded (i.e., graded over a finite rank
free abelian group `\ZZ^n`); if multi-graded, the total degree is used
in the Koszul sign convention, and the differential must have total
degree 1.

EXAMPLES:

All of these algebras may be constructed with the function
:func:`GradedCommutativeAlgebra`. For most users, that will be the
main function of interest. See its documentation for many more
examples.

We start by constructing some graded commutative algebras. Generators
have degree 1 by default::

    sage: A.<x,y,z> = GradedCommutativeAlgebra(QQ)
    sage: x.degree()
    1
    sage: x^2
    0
    sage: y*x
    -x*y
    sage: B.<a,b> = GradedCommutativeAlgebra(QQ, degrees = (2,3))
    sage: a.degree()
    2
    sage: b.degree()
    3

Once we have defined a graded commutative algebra, it is easy to
define a differential on it using the :meth:`GCAlgebra.cdg_algebra` method::

    sage: A.<x,y,z> = GradedCommutativeAlgebra(QQ, degrees=(1,1,2))
    sage: B = A.cdg_algebra({x: x*y, y: -x*y})
    sage: B
    Commutative Differential Graded Algebra with generators ('x', 'y', 'z') in degrees (1, 1, 2) over Rational Field with differential:
        x --> x*y
        y --> -x*y
        z --> 0

AUTHORS:

- Miguel Marco, John Palmieri (2014-07): initial version
"""

#*****************************************************************************
#       Copyright (C) 2014 Miguel Marco <mmarco@unizar.es>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#                  http://www.gnu.org/licenses/
#*****************************************************************************

from sage.structure.unique_representation import UniqueRepresentation
from sage.structure.sage_object import SageObject
from sage.misc.cachefunc import cached_method
from sage.misc.functional import is_odd, is_even
from sage.misc.misc_c import prod
from sage.categories.algebras import Algebras
from sage.categories.morphism import Morphism
from sage.categories.modules import Modules
from sage.categories.homset import Hom

from sage.algebras.free_algebra import FreeAlgebra
from sage.combinat.free_module import CombinatorialFreeModule
from sage.combinat.integer_vector_weighted import WeightedIntegerVectors
from sage.groups.additive_abelian.additive_abelian_group import AdditiveAbelianGroup
from sage.matrix.constructor import matrix
from sage.modules.free_module import VectorSpace
from sage.modules.free_module_element import vector
from sage.rings.all import ZZ
from sage.rings.polynomial.term_order import TermOrder
from sage.rings.quotient_ring import QuotientRing_nc
from sage.rings.quotient_ring_element import QuotientRingElement

class Differential(UniqueRepresentation, Morphism):
    r"""
    Differential of a commutative graded algebra.

    INPUT:

    - ``A`` -- algebra where the differential is defined
    - ``im_gens`` -- tuple containing the image of each generator

    EXAMPLES::

        sage: A.<x,y,z,t> = GradedCommutativeAlgebra(QQ, degrees=(1,1,2,3))
        sage: B = A.cdg_algebra({x: x*y, y: -x*y , z: t})
        sage: B
        Commutative Differential Graded Algebra with generators ('x', 'y', 'z', 't') in degrees (1, 1, 2, 3) over Rational Field with differential:
            x --> x*y
            y --> -x*y
            z --> t
            t --> 0
        sage: B.differential()(x)
        x*y
    """
    @staticmethod
    def __classcall__(cls, A, im_gens):
        r"""
        Normalize input to ensure a unique representation.

        TESTS::

            sage: A.<x,y,z,t> = GradedCommutativeAlgebra(QQ, degrees=(1,1,2,3))
            sage: d1 = A.cdg_algebra({x: x*y, y: -x*y, z: t}).differential()
            sage: d2 = A.cdg_algebra({x: x*y, z: t, y: -x*y, t: 0}).differential()
            sage: d1 is d2
            True
        """
        if isinstance(im_gens, (list, tuple)):
            im_gens = {A.gen(i): x for i,x in enumerate(im_gens)}

        R = A.cover_ring()
        I = A.defining_ideal()
        if A.base_ring().characteristic() != 2:
            squares = R.ideal([R.gen(i)**2 for i,d in enumerate(A._degrees)
                               if is_odd(d)], side='twosided')
        else:
            squares = R.ideal(0, side='twosided')

        if I != squares:
            A_free = GCAlgebra(A.base(), names=A._names, degrees=A._degrees)
            free_diff = {A_free(a): A_free(im_gens[a]) for a in im_gens}
            B = A_free.cdg_algebra(free_diff)
            IB = B.ideal([B(g) for g in I.gens()])
            BQ = GCAlgebra.quotient(B, IB)
            # We check that the differential respects the
            # relations in the quotient method, but we also have
            # to check this here, in case a GCAlgebra with
            # relations is defined first, and then a differential
            # imposed on it.
            for g in IB.gens():
                if not BQ(g.differential()).is_zero():
                    raise ValueError("The differential does not preserve the ideal")

        im_gens = {A(a): A(im_gens[a]) for a in im_gens}

        for i in im_gens:
            x = im_gens[i]
            if (not x.is_zero()
                    and (not x.is_homogeneous() or
                         total_degree(x.degree()) != total_degree(i.degree())+1)):
                raise ValueError("The given dictionary does not determine a degree 1 map")

        im_gens = tuple(im_gens.get(x, A.zero()) for x in A.gens())
        return super(Differential, cls).__classcall__(cls, A, im_gens)

    def __init__(self, A, im_gens):
        r"""
        Initialize ``self``.

        INPUT:

        - ``A`` -- algebra where the differential is defined

        - ``im_gens`` -- tuple containing the image of each generator

        EXAMPLES::

            sage: A.<x,y,z,t> = GradedCommutativeAlgebra(QQ)
            sage: B = A.cdg_algebra({x: x*y, y: x*y, z: z*t, t: t*z})
            sage: [B.cohomology(i).dimension() for i in range(6)]
            [1, 2, 1, 0, 0, 0]
            sage: d = B.differential()

        We skip the category test because homsets/morphisms aren't
        proper parents/elements yet::

            sage: TestSuite(d).run(skip="_test_category")

        An error is raised if the differential `d` does not have
        degree 1 or if `d \circ d` is not zero::

            sage: A.<a,b,c> = GradedCommutativeAlgebra(QQ, degrees=(1,2,3))
            sage: A.cdg_algebra({a:b, b:c})
            Traceback (most recent call last):
            ...
            ValueError: The given dictionary does not determine a valid differential
        """
        self._dic_ = {A.gen(i): x for i,x in enumerate(im_gens)}
        Morphism.__init__(self, Hom(A, A, category=Modules(A.base_ring())))

        for i in A.gens():
            if not self(self(i)).is_zero():
                raise ValueError("The given dictionary does not determine a valid differential")

    def _call_(self, x):
        r"""
        Apply the differential to ``x``.

        INPUT:

        - ``x`` -- an element of the domain of this differential

        EXAMPLES::

            sage: A.<x,y,z,t> = GradedCommutativeAlgebra(QQ)
            sage: B = A.cdg_algebra({x: x*y, y: x*y, z: z*t, t: t*z})
            sage: D = B.differential()
            sage: D(x*t+1/2*t*x*y) # indirect doctest
            -1/2*x*y*z*t + x*y*t + x*z*t

        Test positive characteristic::

            sage: A.<x,y> = GradedCommutativeAlgebra(GF(17), degrees=(2,3))
            sage: B = A.cdg_algebra(differential={x:y})
            sage: B.differential()(x^17)
            0
        """
        if x.is_zero():
            return self.codomain().zero()
        res = self.codomain().zero()
        dic = x.dict()
        for key in dic:
            keyl = list(key)
            coef = dic[key]
            idx = 0
            while keyl:
                exp = keyl.pop(0)
                if exp > 0:
                    v1 = (exp * self._dic_[x.parent().gen(idx)]
                          * x.parent().gen(idx)**(exp-1))
                    v2 = prod(x.parent().gen(i+idx+1)**keyl[i] for i in
                              range(len(keyl)))
                    res += coef*v1*v2
                    coef *= ((-1) ** total_degree(x.parent()._degrees[idx])
                             * x.parent().gen(idx)**exp)
                idx += 1
        return res

    def _repr_defn(self):
        """
        Return a string showing where ``self`` sends each generator.

        EXAMPLES::

            sage: A.<x,y,z,t> = GradedCommutativeAlgebra(QQ)
            sage: B = A.cdg_algebra({x: x*y, y: x*y, z: z*t, t: t*z})
            sage: D = B.differential()
            sage: print D._repr_defn()
            x --> x*y
            y --> x*y
            z --> z*t
            t --> -z*t
        """
        return '\n'.join("{} --> {}".format(i, self(i)) for i in self.domain().gens())

    def _repr_(self):
        r"""
        Return a string representation of ``self``.

        EXAMPLES::

            sage: A.<x,y,z,t> = GradedCommutativeAlgebra(QQ)
            sage: D = A.differential({x: x*y, y: x*y, z: z*t, t: t*z})
            sage: D
            Differential of Graded Commutative Algebra with generators ('x', 'y', 'z', 't') in degrees (1, 1, 1, 1) over Rational Field
              Defn: x --> x*y
                    y --> x*y
                    z --> z*t
                    t --> -z*t
        """
        if self.domain() is None:
            return "Defunct morphism"

        s = "Differential of {}".format(self.domain()._base_repr())
        s += "\n  Defn: " + '\n        '.join(self._repr_defn().split('\n'))
        return s

    @cached_method
    def differential_matrix(self, n):
        r"""
        The matrix that gives the differential in degree ``n``.

        INPUT:

        - ``n`` -- degree

        EXAMPLES::

            sage: A.<x,y,z,t> = GradedCommutativeAlgebra(GF(5), degrees=(2, 3, 2, 4))
            sage: d = A.differential({t: x*y, x: y, z: y})
            sage: d.differential_matrix(4)
            [0 1]
            [2 0]
            [1 1]
            [0 2]
            sage: A.inject_variables()
            Defining x, y, z, t
            sage: d(t)
            x*y
            sage: d(z^2)
            2*y*z
            sage: d(x*z)
            x*y + y*z
            sage: d(x^2)
            2*x*y
        """
        A = self.domain()
        dom = A.basis(n)
        cod = A.basis(n+1)
        cokeys = [a.lift().dict().keys()[0] for a in cod]
        m = matrix(A.base_ring(), len(dom), len(cod))
        for i in range(len(dom)):
            im = self(dom[i])
            dic = im.lift().dict()
            for j in dic.keys():
                k = cokeys.index(j)
                m[i,k] = dic[j]
        m.set_immutable()
        return m

    def coboundaries(self, n):
        r"""
        The ``n``-th coboundary group of the algebra.

        This is a vector space over the base field `F`, and it is
        returned as a subspace of the vector space `F^d`, where the
        ``n``-th homogeneous component has dimension `d`.

        INPUT:

        - ``n`` -- degree

        EXAMPLES::

            sage: A.<x,y,z> = GradedCommutativeAlgebra(QQ, degrees=(1,1,2))
            sage: d = A.differential({z: x*z})
            sage: d.coboundaries(2)
            Vector space of degree 2 and dimension 0 over Rational Field
            Basis matrix:
            []
            sage: d.coboundaries(3)
            Vector space of degree 2 and dimension 1 over Rational Field
            Basis matrix:
            [0 1]
        """
        A = self.domain()
        F = A.base_ring()
        if n == 0:
            return VectorSpace(F, 0)
        if n == 1:
            return VectorSpace(F, 0)
        M = self.differential_matrix(n-1)
        V0 = VectorSpace(F, M.nrows())
        V1 = VectorSpace(F, M.ncols())
        mor = V0.Hom(V1)(M)
        return mor.image()

    def cocycles(self, n):
        r"""
        The ``n``-th cocycle group of the algebra.

        This is a vector space over the base field `F`, and it is
        returned as a subspace of the vector space `F^d`, where the
        ``n``-th homogeneous component has dimension `d`.

        INPUT:

        - ``n`` -- degree

        EXAMPLES::

            sage: A.<x,y,z> = GradedCommutativeAlgebra(QQ, degrees=(1,1,2))
            sage: d = A.differential({z: x*z})
            sage: d.cocycles(2)
            Vector space of degree 2 and dimension 1 over Rational Field
            Basis matrix:
            [1 0]
        """
        A = self.domain()
        F = A.base_ring()
        if n == 0:
            return VectorSpace(F, 1)
        M = self.differential_matrix(n)
        V0 = VectorSpace(F, M.nrows())
        V1 = VectorSpace(F, M.ncols())
        mor = V0.Hom(V1)(M)
        return mor.kernel()

    def cohomology_raw(self, n):
        r"""
        The ``n``-th cohomology group of ``self``.

        This is a vector space over the base ring, and it is returned
        as the quotient cocycles/coboundaries.

        INPUT:

        - ``n`` -- degree

        .. SEEALSO::

            :meth:`cohomology`

        EXAMPLES::

            sage: A.<x,y,z,t> = GradedCommutativeAlgebra(QQ, degrees=(2,3,2,4))
            sage: d = A.differential({t: x*y, x: y, z: y})
            sage: d.cohomology_raw(4)
            Vector space quotient V/W of dimension 2 over Rational Field where
            V: Vector space of degree 4 and dimension 2 over Rational Field
            Basis matrix:
            [   1    0    0 -1/2]
            [   0    1   -2    1]
            W: Vector space of degree 4 and dimension 0 over Rational Field
            Basis matrix:
            []

        Compare to :meth:`cohomology`::

            sage: d.cohomology(4)
            Free module generated by {[-1/2*x^2 + t], [x^2 - 2*x*z + z^2]} over Rational Field
        """
        return self.cocycles(n).quotient(self.coboundaries(n))

    def cohomology(self, n):
        r"""
        The ``n``-th cohomology group of ``self``.

        This is a vector space over the base ring, defined as the
        quotient cocycles/coboundaries. The elements of the quotient
        are lifted to the vector space of cocycles, and this is
        described in terms of those lifts.

        INPUT:

        - ``n`` -- degree

        .. SEEALSO::

            :meth:`cohomology_raw`

        EXAMPLES::

            sage: A.<a,b,c,d,e> = GradedCommutativeAlgebra(QQ, degrees=(1,1,1,1,1))
            sage: d = A.differential({d: a*b, e: b*c})
            sage: d.cohomology(2)
            Free module generated by {[c*e], [c*d - a*e], [b*e], [b*d], [a*d], [a*c]} over Rational Field

        Compare to :meth:`cohomology_raw`::

            sage: d.cohomology_raw(2)
            Vector space quotient V/W of dimension 6 over Rational Field where
            V: Vector space of degree 10 and dimension 8 over Rational Field
            Basis matrix:
            [ 0  1  0  0  0  0  0  0  0  0]
            [ 0  0  1  0  0  0 -1  0  0  0]
            [ 0  0  0  1  0  0  0  0  0  0]
            [ 0  0  0  0  1  0  0  0  0  0]
            [ 0  0  0  0  0  1  0  0  0  0]
            [ 0  0  0  0  0  0  0  1  0  0]
            [ 0  0  0  0  0  0  0  0  1  0]
            [ 0  0  0  0  0  0  0  0  0  1]
            W: Vector space of degree 10 and dimension 2 over Rational Field
            Basis matrix:
            [0 0 0 0 0 1 0 0 0 0]
            [0 0 0 0 0 0 0 0 0 1]
        """
        H = self.cohomology_raw(n)
        H_basis_raw = [H.lift(H.basis()[i]) for i in range(H.dimension())]
        A = self.domain()
        B = A.basis(n)
        H_basis = [sum([c*b for (c,b) in zip(coeffs, B)]) for coeffs in H_basis_raw]
        # Put brackets around classes.
        H_basis_brackets = [CohomologyClass(b) for b in H_basis]
        return CombinatorialFreeModule(A.base_ring(), H_basis_brackets)

class Differential_multigraded(Differential):
    """
    Differential of a commutative multigraded algebra.
    """
    def __init__(self, A, im_gens):
        """
        Initialize ``self``.

        EXAMPLES::

            sage: A.<a,b,c> = GradedCommutativeAlgebra(QQ, degrees=((1,0), (0, 1), (0,2)))
            sage: d = A.differential({a: c})

        We skip the category test because homsets/morphisms aren't
        proper parents/elements yet::

            sage: TestSuite(d).run(skip="_test_category")
        """
        Differential.__init__(self, A, im_gens)

        # Check that the differential has a well-defined degree.
        # diff_deg = [self(x).degree() - x.degree() for x in A.gens()]
        diff_deg = []
        for x in A.gens():
            y = self(x)
            if y != 0:
                diff_deg.append(y.degree() - x.degree())
        if len(set(diff_deg)) > 1:
            raise ValueError("The differential does not have a well-defined degree")
        self._degree_of_differential = diff_deg[0]

    @cached_method
    def differential_matrix_multigraded(self, n, total=False):
        """
        The matrix that gives the differential in degree ``n``.

        .. TODO::

            Rename this to ``differential_matrix`` once inheritance,
            overriding, and cached methods work together better. See
            :trac:`17201`.

        INPUT:

        - ``n`` -- degree
        - ``total`` -- (default: ``False``) if ``True``,
          return the matrix corresponding to total degree ``n``

        If ``n`` is an integer rather than a multi-index, then the
        total degree is used in that case as well.

        EXAMPLES::

            sage: A.<a,b,c> = GradedCommutativeAlgebra(QQ, degrees=((1,0), (0, 1), (0,2)))
            sage: d = A.differential({a: c})
            sage: d.differential_matrix_multigraded((1,0))
            [1]
            sage: d.differential_matrix_multigraded(1, total=True)
            [0 0]
            [0 1]
            sage: d.differential_matrix_multigraded((1,0), total=True)
            [0 0]
            [0 1]
            sage: d.differential_matrix_multigraded(1)
            [0 0]
            [0 1]
        """
        if total or n in ZZ:
            return Differential.differential_matrix(self, total_degree(n))

        A = self.domain()
        G = AdditiveAbelianGroup([0] * A._grading_rank)
        n = G(vector(n))
        dom = A.basis(n)
        cod = A.basis(n+self._degree_of_differential)
        cokeys = [a.lift().dict().keys()[0] for a in cod]
        m = matrix(self.base_ring(), len(dom), len(cod))
        for i in range(len(dom)):
            im = self(dom[i])
            dic = im.lift().dict()
            for j in dic.keys():
                k = cokeys.index(j)
                m[i,k] = dic[j]
        m.set_immutable()
        return m

    def coboundaries(self, n, total=False):
        """
        The ``n``-th coboundary group of the algebra.

        This is a vector space over the base field `F`, and it is
        returned as a subspace of the vector space `F^d`, where the
        ``n``-th homogeneous component has dimension `d`.

        INPUT:

        - ``n`` -- degree
        - ``total`` (default ``False``) -- if ``True``, return the
          coboundaries in total degree ``n``

        If ``n`` is an integer rather than a multi-index, then the
        total degree is used in that case as well.

        EXAMPLES::

            sage: A.<a,b,c> = GradedCommutativeAlgebra(QQ, degrees=((1,0), (0, 1), (0,2)))
            sage: d = A.differential({a: c})
            sage: d.coboundaries((0,2))
            Vector space of degree 1 and dimension 1 over Rational Field
            Basis matrix:
            [1]
            sage: d.coboundaries(2)
            Vector space of degree 2 and dimension 1 over Rational Field
            Basis matrix:
            [0 1]
        """
        if total or n in ZZ:
            return Differential.coboundaries(self, total_degree(n))

        A = self.domain()
        G = AdditiveAbelianGroup([0] * A._grading_rank)
        n = G(vector(n))
        F = A.base_ring()
        if total_degree(n) == 0:
            return VectorSpace(F, 0)
        if total_degree(n) == 1:
            return VectorSpace(F, 0)
        M = self.differential_matrix_multigraded(n-self._degree_of_differential)
        V0 = VectorSpace(F, M.nrows())
        V1 = VectorSpace(F, M.ncols())
        mor = V0.Hom(V1)(M)
        return mor.image()

    def cocycles(self, n, total=False):
        r"""
        The ``n``-th cocycle group of the algebra.

        This is a vector space over the base field `F`, and it is
        returned as a subspace of the vector space `F^d`, where the
        ``n``-th homogeneous component has dimension `d`.

        INPUT:

        - ``n`` -- degree
        - ``total`` -- (default: ``False``) if ``True``, return the
          cocycles in total degree ``n``

        If ``n`` is an integer rather than a multi-index, then the
        total degree is used in that case as well.

        EXAMPLES::

            sage: A.<a,b,c> = GradedCommutativeAlgebra(QQ, degrees=((1,0), (0, 1), (0,2)))
            sage: d = A.differential({a: c})
            sage: d.cocycles((0,1))
            Vector space of degree 1 and dimension 1 over Rational Field
            Basis matrix:
            [1]
            sage: d.cocycles((0,1), total=True)
            Vector space of degree 2 and dimension 1 over Rational Field
            Basis matrix:
            [1 0]
        """
        if total or n in ZZ:
            return Differential.cocycles(self, total_degree(n))

        A = self.domain()
        G = AdditiveAbelianGroup([0] * A._grading_rank)
        n = G(vector(n))
        F = A.base_ring()
        if total_degree(n) == 0:
            return VectorSpace(F, 1)
        M = self.differential_matrix_multigraded(n)
        V0 = VectorSpace(F, M.nrows())
        V1 = VectorSpace(F, M.ncols())
        mor = V0.Hom(V1)(M)
        return mor.kernel()

    def cohomology_raw(self, n, total=False):
        r"""
        The ``n``-th cohomology group of the algebra.

        This is a vector space over the base ring, and it is returned
        as the quotient cocycles/coboundaries.

        INPUT:

        - ``n`` -- degree
        - ``total`` -- (default: ``False``) if ``True``, return the
          cohomology in total degree ``n``

        If ``n`` is an integer rather than a multi-index, then the
        total degree is used in that case as well.

        .. SEEALSO::

            :meth:`cohomology`

        EXAMPLES::

            sage: A.<a,b,c> = GradedCommutativeAlgebra(QQ, degrees=((1,0), (0, 1), (0,2)))
            sage: d = A.differential({a: c})
            sage: d.cohomology_raw((0,2))
            Vector space quotient V/W of dimension 0 over Rational Field where
            V: Vector space of degree 1 and dimension 1 over Rational Field
            Basis matrix:
            [1]
            W: Vector space of degree 1 and dimension 1 over Rational Field
            Basis matrix:
            [1]

            sage: d.cohomology_raw(1)
            Vector space quotient V/W of dimension 1 over Rational Field where
            V: Vector space of degree 2 and dimension 1 over Rational Field
            Basis matrix:
            [1 0]
            W: Vector space of degree 2 and dimension 0 over Rational Field
            Basis matrix:
            []
        """
        return self.cocycles(n, total).quotient(self.coboundaries(n, total))

    def cohomology(self, n, total=False):
        r"""
        The ``n``-th cohomology group of the algebra.

        This is a vector space over the base ring, defined as the
        quotient cocycles/coboundaries. The elements of the quotient
        are lifted to the vector space of cocycles, and this is
        described in terms of those lifts.

        INPUT:

        - ``n`` -- degree
        - ``total`` -- (default: ``False``) if ``True``, return the
          cohomology in total degree ``n``

        If ``n`` is an integer rather than a multi-index, then the
        total degree is used in that case as well.

        .. SEEALSO::

            :meth:`cohomology_raw`

        EXAMPLES::

            sage: A.<a,b,c> = GradedCommutativeAlgebra(QQ, degrees=((1,0), (0, 1), (0,2)))
            sage: d = A.differential({a: c})
            sage: d.cohomology((0,2))
            Free module generated by {} over Rational Field

            sage: d.cohomology(1)
            Free module generated by {[b]} over Rational Field
        """
        H = self.cohomology_raw(n, total)
        H_basis_raw = [H.lift(H.basis()[i]) for i in range(H.dimension())]
        A = self.domain()
        B = A.basis(n, total)
        H_basis = [sum([c*b for (c,b) in zip(coeffs, B)]) for coeffs in H_basis_raw]
        # Put brackets around classes.
        H_basis_brackets = [CohomologyClass(b) for b in H_basis]
        return CombinatorialFreeModule(A.base_ring(), H_basis_brackets)

###########################################################
## Commutative graded algebras

class GCAlgebra(UniqueRepresentation, QuotientRing_nc):
    r"""
    A graded commutative algebra.

    INPUT:

    - ``base`` -- the base field

    - ``names`` -- (optional) names of the generators: a list of
      strings or a single string with the names separated by
      commas. If not specified, the generators are named "x0", "x1",
      ...

    - ``degrees`` -- (optional) a tuple or list specifying the degrees
      of the generators; if omitted, each generator is given degree
      1, and if both ``names`` and ``degrees`` are omitted, an error is
      raised.

    - ``R`` (optional, default None) -- the ring over which the
      algebra is defined: if this is specified, the algebra is defined
      to be ``R/I``.

    - ``I`` (optional, default None) -- an ideal in ``R``. It is
      should include, among other relations, the squares of the
      generators of odd degree

    As described in the module-level documentation, these are graded
    algebras for which oddly graded elements anticommute and evenly
    graded elements commute.

    The arguments ``R`` and ``I`` are primarily for use by the
    :meth:`quotient` method.

    These algebras should be graded over the integers; multi-graded
    algebras should be constructed using
    :class:`GCAlgebra_multigraded` instead.

    EXAMPLES::

        sage: A.<a,b> = GradedCommutativeAlgebra(QQ, degrees = (2,3))
        sage: a.degree()
        2
        sage: B = A.quotient(A.ideal(a**2*b))
        sage: B
        Graded Commutative Algebra with generators ('a', 'b') in degrees (2, 3) with relations [a^2*b] over Rational Field
        sage: A.basis(7)
        [a^2*b]
        sage: B.basis(7)
        []

    Note that the function :func:`GradedCommutativeAlgebra` can also be used to
    construct these algebras.
    """
    # TODO: This should be a __classcall_private__?
    @staticmethod
    def __classcall__(cls, base, names=None, degrees=None, R=None, I=None):
        r"""
        Normalize the input for the :meth:`__init__` method and the
        unique representation.

        INPUT:

        - ``base`` -- the base ring of the algebra

        - ``names`` -- the names of the variables; by default, set to ``x1``,
          ``x2``, etc.

        - ``degrees`` -- the degrees of the generators; by default, set to 1

        - ``R`` -- an underlying `g`-algebra; only meant to be used by the
          quotient method

        - ``I`` -- a two-sided ideal in ``R``, with the desired relations;
          Only meant to be used by the quotient method

        TESTS::

            sage: A1 = GradedCommutativeAlgebra(GF(2), 'x,y', (3, 6))
            sage: A2 = GradedCommutativeAlgebra(GF(2), ['x', 'y'], [3, 6])
            sage: A1 is A2
            True
        """
        if names is None:
            if degrees is None:
                raise ValueError("You must specify names or degrees")
            else:
                n = len(degrees)
            names = tuple('x{}'.format(i) for i in range(n))
        elif isinstance(names, basestring):
            names = tuple(names.split(','))
            n = len(names)
        else:
            n = len(names)
            names = tuple(names)

        if degrees is None:
            degrees = tuple([1 for i in range(n)])
        else:
            # Deal with multigrading: convert lists and tuples to elements
            # of an additive abelian group.
            if len(degrees) > 0:
                try:
                    rank = len(list(degrees[0]))
                    G = AdditiveAbelianGroup([0]*rank)
                    degrees = [G(vector(d)) for d in degrees]
                except TypeError:
                    # The entries of degrees are not iterables, so
                    # treat as singly-graded.
                    pass
            degrees = tuple(degrees)

        if not R or not I:
            F = FreeAlgebra(base, n, names)
            gens = F.gens()
            rels = {}
            tot_degs = [total_degree(d) for d in degrees]
            for i in range(len(gens)-1):
                for j in range(i+1, len(gens)):
                    rels[gens[j]*gens[i]] = ((-1) ** (tot_degs[i] * tot_degs[j])
                                             * gens[i] * gens[j])
            R = F.g_algebra(rels, order = TermOrder('wdegrevlex', tot_degs))
            if base.characteristic() == 2:
                I = R.ideal(0, side='twosided')
            else:
                I = R.ideal([R.gen(i)**2 for i in range(n) if is_odd(tot_degs[i])],
                            side='twosided')

        return super(GCAlgebra, cls).__classcall__(cls, base=base, names=names,
                                                   degrees=degrees, R=R, I=I)

    def __init__(self, base, R=None, I=None, names=None, degrees=None):
        """
        Initialize ``self``.

        INPUT:

        - ``base`` -- the base field

        - ``R`` -- (optional) the ring over which the algebra is defined

        - ``I`` -- (optional) an ideal over the corresponding `g`-algebra;
          it is meant to include, among other relations, the squares of the
          generators of odd degree

        - ``names`` -- (optional) the names of the generators; if omitted,
          this uses the names ``x0``, ``x1``, ...

        - ``degrees`` -- (optional) the degrees of the generators; if
          omitted, they are given degree 1

        EXAMPLES::

            sage: A.<x,y,z,t> = GradedCommutativeAlgebra(QQ)
            sage: TestSuite(A).run()
            sage: A = GradedCommutativeAlgebra(QQ, ('x','y','z'), [3,4,2])
            sage: TestSuite(A).run()
            sage: A = GradedCommutativeAlgebra(QQ, ('x','y','z','t'), [3, 4, 2, 1])
            sage: TestSuite(A).run()
        """
        self._degrees = tuple(degrees)
        cat = Algebras(R.base_ring()).Graded()
        QuotientRing_nc.__init__(self, R, I, names, category=cat)

    def _repr_(self):
        """
        Print representation.

        EXAMPLES::

            sage: A.<x,y,z,t> = GradedCommutativeAlgebra(QQ, degrees=[3, 4, 2, 1])
            sage: A
            Graded Commutative Algebra with generators ('x', 'y', 'z', 't') in degrees (3, 4, 2, 1) over Rational Field
            sage: A.quotient(A.ideal(3*x*z - 2*y*t))
            Graded Commutative Algebra with generators ('x', 'y', 'z', 't') in degrees (3, 4, 2, 1) with relations [3*x*z - 2*y*t] over Rational Field 
        """
        s = "Graded Commutative Algebra with generators {} in degrees {}".format(self._names, self._degrees)
        # Find any nontrivial relations.
        I = self.defining_ideal()
        R = self.cover_ring()
        degrees = self._degrees
        if self.base().characteristic() != 2:
            squares = [R.gen(i)**2 for i in range(len(degrees)) if is_odd(degrees[i])]
        else:
            squares = [R.zero()]
        relns = [g for g in I.gens() if g not in squares]
        if relns:
            s = s + " with relations {}".format(relns)
        return s + " over {}".format(self.base_ring())

    _base_repr = _repr_

    @cached_method
    def _basis_for_free_alg(self, n):
        r"""
        Basis of the associated free commutative DGA in degree ``n``.

        That is, ignore the relations when computing the basis:
        compute the basis of the free commutative DGA with generators
        in degrees given by ``self._degrees``.

        INPUT:

        - ``n`` -- integer

        OUTPUT:

        Tuple of basis elements in degree ``n``, as tuples of exponents.

        EXAMPLES::

            sage: A.<a,b,c> = GradedCommutativeAlgebra(QQ, degrees=(1,2,3))
            sage: A._basis_for_free_alg(3)
            [(0, 0, 1), (1, 1, 0)]
            sage: B = A.quotient(A.ideal(a*b, b**2+a*c))
            sage: B._basis_for_free_alg(3)
            [(0, 0, 1), (1, 1, 0)]

            sage: GradedCommutativeAlgebra(QQ, degrees=(1,1))._basis_for_free_alg(3)
            []
            sage: GradedCommutativeAlgebra(GF(2), degrees=(1,1))._basis_for_free_alg(3)
            [(0, 3), (1, 2), (2, 1), (3, 0)]

            sage: A = GradedCommutativeAlgebra(GF(2), degrees=(4,8,12))
            sage: A._basis_for_free_alg(399)
            []
        """
        if n == 0:
            return ((0,)*len(self._degrees),)
        if self.base_ring().characteristic() == 2:
            return [tuple(_) for _ in WeightedIntegerVectors(n, self._degrees)]

        even_degrees = []
        odd_degrees = []
        for a in self._degrees:
            if is_even(a):
                even_degrees.append(a)
            else:
                odd_degrees.append(a)

        if not even_degrees: # No even generators.
            return [tuple(_) for _ in exterior_algebra_basis(n, tuple(odd_degrees))]
        if not odd_degrees: # No odd generators.
            return [tuple(_) for _ in WeightedIntegerVectors(n, tuple(even_degrees))]

        # General case: both even and odd generators.
        result = []
        for dim in range(n+1):
            # First find the even part of the basis.
            if dim == 0:
                even_result = [[0]*len(even_degrees)]
            else:
                even_result = WeightedIntegerVectors(dim, tuple(even_degrees))
            # Now find the odd part of the basis.
            for even_mono in even_result:
                deg = n - dim
                odd_result = exterior_algebra_basis(deg, tuple(odd_degrees))
                for odd_mono in odd_result:
                    temp_even = list(even_mono)
                    temp_odd = list(odd_mono)
                    mono = []
                    for a in self._degrees:
                        if is_even(a):
                            mono.append(temp_even.pop(0))
                        else:
                            mono.append(temp_odd.pop(0))
                    result.append(tuple(mono))
        return result

    def basis(self, n):
        """
        Return a basis of the ``n``-th homogeneous component of ``self``.

        EXAMPLES::

            sage: A.<x,y,z,t> = GradedCommutativeAlgebra(QQ, degrees=(1, 2, 2, 3))
            sage: A.basis(2)
            [z, y]
            sage: A.basis(3)
            [t, x*z, x*y]
            sage: A.basis(4)
            [x*t, z^2, y*z, y^2]
            sage: A.basis(5)
            [z*t, y*t, x*z^2, x*y*z, x*y^2]
            sage: A.basis(6)
            [x*z*t, x*y*t, z^3, y*z^2, y^2*z, y^3]
        """
        free_basis = self._basis_for_free_alg(n)
        basis = []
        for v in free_basis:
            el = prod([self.gen(i)**v[i] for i in range(len(v))])
            di = el.dict()
            if len(di) == 1:
                if tuple(di.keys()[0]) == v:
                    basis.append(el)
        return basis

    def quotient(self, I, check=True):
        """
        Create the quotient of this algebra by a two-sided ideal ``I``.

        INPUT:

        - ``I`` -- a two-sided homogeneous ideal of this algebra

        - ``check`` -- (default: ``True``) if ``True``, check whether
          ``I`` is generated by homogeneous elements

        EXAMPLES::

            sage: A.<x,y,z,t> = GradedCommutativeAlgebra(GF(5), degrees=(2, 3, 2, 4))
            sage: I = A.ideal([x*t+y^2, x*z - t])
            sage: B = A.quotient(I)
            sage: B
            Graded Commutative Algebra with generators ('x', 'y', 'z', 't') in degrees (2, 3, 2, 4) with relations [x*t, x*z - t] over Finite Field of size 5
            sage: B(x*t)
            0
            sage: B(x*z)
            t
            sage: A.basis(7)
            [y*t, y*z^2, x*y*z, x^2*y]
            sage: B.basis(7)
            [y*t, y*z^2, x^2*y]
        """
        if check and any(not i.is_homogeneous() for i in I.gens()):
            raise ValueError("The ideal must be homogeneous")
        NCR = self.cover_ring()
        gens1 = list(self.defining_ideal().gens())
        gens2 = [i.lift() for i in I.gens()]
        gens = [g for g in gens1 + gens2 if g != NCR.zero()]
        J = NCR.ideal(gens, side='twosided')
        return GCAlgebra(self.base_ring(), self._names, self._degrees, NCR, J)

    def _coerce_map_from_(self, other):
        r"""
        Returns ``True`` if there is a coercion map from ``R`` to ``self``.

        EXAMPLES::

            sage: A.<x,y,z> = GradedCommutativeAlgebra(QQ, degrees=(2,1,1))
            sage: B = A.cdg_algebra({y:y*z, z: y*z})
            sage: A._coerce_map_from_(B)
            True
            sage: B._coerce_map_from_(A)
            True
            sage: B._coerce_map_from_(QQ)
            True
            sage: B._coerce_map_from_(GF(3))
            False
        """
        if isinstance(other, GCAlgebra):
            if self._names != other._names or self._degrees != other._degrees:
                return False
            if set(self.defining_ideal().gens()) != set(other.defining_ideal().gens()):
                return False
            return self.cover_ring().has_coerce_map_from(other.cover_ring())
        return super(GCAlgebra, self)._coerce_map_from_(other)

    def _element_constructor_(self, x, coerce=True):
        r"""
        EXAMPLES::

            sage: A.<x,y,z,t> = GradedCommutativeAlgebra(QQ, degrees=(2, 3, 2, 4))
            sage: A({(1,0,3,1): 2, (2,1,2,2): 3})
            3*x^2*y*z^2*t^2 + 2*x*z^3*t
            sage: A.<x,y,z,t> = GradedCommutativeAlgebra(GF(5))
            sage: A({(1,0,3,1): 2, (2,1,2,2): 3})
            0
        """
        if isinstance(x, QuotientRingElement):
            if x.parent() is self:
                return x
            x = x.lift()
        if isinstance(x, dict):
            res = self.zero()
            for i in x.keys():
                mon = prod(self.gen(j)**i[j] for j in range(len(i)))
                res += x[i]*mon
            return res
        if coerce:
            R = self.cover_ring()
            x = R(x)

        from sage.interfaces.singular import is_SingularElement
        if is_SingularElement(x):
            #self._singular_().set_ring()
            x = self.element_class(self, x.sage_poly(self.cover_ring()))
            return x

        return self.element_class(self, x)

    def differential(self, diff):
        """
        Construct a differential on ``self``.

        INPUT:

        - ``diff`` -- a dictionary defining a differential

        The keys of the dictionary are generators of the algebra, and
        the associated values are their targets under the
        differential. Any generators which are not specified are
        assumed to have zero differential.

        EXAMPLES::

            sage: A.<x,y,z> = GradedCommutativeAlgebra(QQ, degrees=(2,1,1))
            sage: A.differential({y:y*z, z: y*z})
            Differential of Graded Commutative Algebra with generators ('x', 'y', 'z') in degrees (2, 1, 1) over Rational Field
              Defn: x --> 0
                    y --> y*z
                    z --> y*z
            sage: B.<a,b,c> = GradedCommutativeAlgebra(QQ, degrees=(1,2,2))
            sage: d = B.differential({b:a*c, c:a*c})
            sage: d(b*c)
            a*b*c + a*c^2
        """
        return Differential(self, diff)

    def cdg_algebra(self, differential):
        r"""
        Construct a differential graded commutative algebra from ``self``
        by specifying a differential.

        INPUT:

        - ``differential`` -- a dictionary defining a differential or
          a map defining a valid differential

        The keys of the dictionary are generators of the algebra, and
        the associated values are their targets under the
        differential. Any generators which are not specified are
        assumed to have zero differential. Alternatively, the
        differential can be defined using the :meth:`differential`
        method; see below for an example.

        .. SEEALSO::

            :meth:`differential`

        EXAMPLES::

            sage: A.<a,b,c> = GradedCommutativeAlgebra(QQ, degrees=(1,1,1))
            sage: B = A.cdg_algebra({a: b*c, b: a*c})
            sage: B
            Commutative Differential Graded Algebra with generators ('a', 'b', 'c') in degrees (1, 1, 1) over Rational Field with differential:
                a --> b*c
                b --> a*c
                c --> 0

        Note that ``differential`` can also be a map::

            sage: d = A.differential({a: b*c, b: a*c})
            sage: d
            Differential of Graded Commutative Algebra with generators ('a', 'b', 'c') in degrees (1, 1, 1) over Rational Field
              Defn: a --> b*c
                    b --> a*c
                    c --> 0
            sage: A.cdg_algebra(d) is B
            True
        """
        return DifferentialGCAlgebra(self, differential)

    # TODO: Do we want a fully spelled out alias?
    # commutative_differential_graded_algebra = cdg_algebra

    class Element(QuotientRingElement):
        r"""
        An element of a graded commutative algebra.
        """
        def __init__(self, A, rep):
            r"""
            Initialize ``self``.

            INPUT:

            - ``parent`` -- the graded commutative algebra in which
              this element lies, viewed as a quotient `R / I`

            - ``rep`` -- a representative of the element in `R`; this is used
              as the internal representation of the element

            EXAMPLES::

                sage: B.<x,y> = GradedCommutativeAlgebra(QQ, degrees=(2, 2))
                sage: a = B({(1,1): -3, (2,5): 1/2})
                sage: a
                1/2*x^2*y^5 - 3*x*y
                sage: TestSuite(a).run()

                sage: b = x^2*y^3+2
                sage: b
                x^2*y^3 + 2
            """
            QuotientRingElement.__init__(self, A, rep)

        def degree(self):
            r"""
            The degree of this element.

            If the element is not homogeneous, this returns the
            maximum of the degrees of its monomials.

            EXAMPLES::

                sage: A.<x,y,z,t> = GradedCommutativeAlgebra(QQ, degrees=(2,3,3,1))
                sage: el = y*z+2*x*t-x^2*y
                sage: el.degree()
                7
                sage: el.monomials()
                [x^2*y, y*z, x*t]
                sage: [i.degree() for i in el.monomials()]
                [7, 6, 3]

                sage: A(0).degree()
                Traceback (most recent call last):
                ...
                ValueError: The zero element does not have a well-defined degree
            """
            if self.is_zero():
                raise ValueError("The zero element does not have a well-defined degree")
            exps = self.lift().dict().keys()
            degrees = self.parent()._degrees
            n = self.parent().ngens()
            l = [sum(e[i] * degrees[i] for i in range(n)) for e in exps]
            return max(l)

        def is_homogeneous(self):
            r"""
            Return ``True`` if ``self`` is homogenous and ``False`` otherwise.

            EXAMPLES::

                sage: A.<x,y,z,t> = GradedCommutativeAlgebra(QQ, degrees=(2,3,3,1))
                sage: el = y*z + 2*x*t - x^2*y
                sage: el.degree()
                7
                sage: el.monomials()
                [x^2*y, y*z, x*t]
                sage: [i.degree() for i in el.monomials()]
                [7, 6, 3]
                sage: el.is_homogeneous()
                False
                sage: em = x^3 - 5*y*z + 3/2*x*z*t
                sage: em.is_homogeneous()
                True
                sage: em.monomials()
                [x^3, y*z, x*z*t]
                sage: [i.degree() for i in em.monomials()]
                [6, 6, 6]

            The element 0 is homogeneous, even though it doesn't have
            a well-defined degree::

                sage: A(0).is_homogeneous()
                True
            """
            degree = None
            for m in self.monomials():
                if degree is None:
                    degree = m.degree()
                else:
                    if degree != m.degree():
                        return False
            return True

        def dict(self):
            r"""
            A dictionary that determines the element.

            The keys of this dictionary are the tuples of exponents of each
            monomial, and the values are the corresponding coefficients.

            EXAMPLES::

                sage: A.<x,y,z,t> = GradedCommutativeAlgebra(QQ, degrees=(1, 2, 2, 3))
                sage: dic = (x*y - 5*y*z + 7*x*y^2*z^3*t).dict()
                sage: sorted(dic.items())
                [((0, 1, 1, 0), -5), ((1, 1, 0, 0), 1), ((1, 2, 3, 1), 7)]
            """
            return self.lift().dict()

        def basis_coefficients(self):
            """
            Return the coefficients of this homogeneous element with
            respect to the basis in its degree.

            For example, if this is the sum of the 0th and 2nd basis
            elements, return the list ``[1, 0, 1]``.

            Raise an error if the element is not homogeneous.

            OUTPUT:

            A list of integers.

            EXAMPLES::

                sage: A.<x,y,z,t> = GradedCommutativeAlgebra(QQ, degrees=(1, 2, 2, 3))
                sage: A.basis(3)
                [t, x*z, x*y]
                sage: (t + 3*x*y).basis_coefficients()
                [1, 0, 3]
                sage: (t + x).basis_coefficients()
                Traceback (most recent call last):
                ...
                ValueError: This element is not homogeneous
            """
            try:
                assert self.is_homogeneous()
            except AssertionError:
                raise ValueError('This element is not homogeneous')

            basis = self.parent().basis(self.degree())
            F = self.parent().base()
            c = [F(0)] * len(basis) # coefficient 'vector'
            dic = self.dict()
            for m in self.monomials():
                c[basis.index(m)] = dic[m.dict().keys()[0]]
            return c

class GCAlgebra_multigraded(GCAlgebra):
    """
    A multi-graded commutative algebra.

    INPUT:

    - ``base`` -- the base field

    - ``degrees`` -- a tuple or list specifying the degrees of the
      generators

    - ``names`` -- (optional) names of the generators: a list of
      strings or a single string with the names separated by
      commas; if not specified, the generators are named ``x0``,
      ``x1``, ...

    - ``R`` -- (optional) the ring over which the algebra is defined

    - ``I`` -- (optional) an ideal in ``R``; it should include, among
      other relations, the squares of the generators of odd degree

    When defining such an algebra, each entry of ``degrees`` should be
    a list, tuple, or element of an additive (free) abelian
    group. Regardless of how the user specifies the degrees, Sage
    converts them to group elements.

    The arguments ``R`` and ``I`` are primarily for use by the
    :meth:`GCAlgebra.quotient` method.

    EXAMPLES::

        sage: A.<a,b,c> = GradedCommutativeAlgebra(QQ, degrees=((1,0), (0,1), (1,1)))
        sage: A
        Graded Commutative Algebra with generators ('a', 'b', 'c') in degrees ((1, 0), (0, 1), (1, 1)) over Rational Field
        sage: a**2
        0
        sage: c.degree(total=True)
        2
        sage: c**2
        c^2
        sage: c.degree()
        (1, 1)

    Although the degree of ``c`` was defined using a Python tuple, it
    is returned as an element of an additive abelian group, and so it
    can be manipulated via arithmetic operations::

        sage: type(c.degree())
        <class 'sage.groups.additive_abelian.additive_abelian_group.AdditiveAbelianGroup_fixed_gens_with_category.element_class'>
        sage: 2 * c.degree()
        (2, 2)
        sage: (a*b).degree() == a.degree() + b.degree()
        True

    The :meth:`basis` method and the :meth:`Element.degree` method both accept
    the boolean keyword ``total``. If ``True``, use the total degree::

        sage: A.basis(2, total=True)
        [a*b, c]
        sage: c.degree(total=True)
        2
    """
    def __init__(self, base, degrees, names=None, R=None, I=None):
        """
        Initialize ``self``.

        EXAMPLES::

            sage: A.<a,b,c> = GradedCommutativeAlgebra(QQ, degrees=((1,0), (0,1), (1,1)))
            sage: TestSuite(A).run()
        """
        total_degs = [total_degree(d) for d in degrees]
        GCAlgebra.__init__(self, base, R=R, I=I, names=names, degrees=total_degs)
        self._degrees_multi = degrees
        self._grading_rank = len(list(degrees[0]))

    def _repr_(self):
        """
        Print representation.

        EXAMPLES::

            sage: GradedCommutativeAlgebra(QQ, degrees=((1,0,0), (0,0,1), (1,1,1)))
            Graded Commutative Algebra with generators ('x0', 'x1', 'x2') in degrees ((1, 0, 0), (0, 0, 1), (1, 1, 1)) over Rational Field
        """
        s = GCAlgebra._repr_(self)
        old = '{}'.format(self._degrees)
        new = '{}'.format(self._degrees_multi)
        return s.replace(old, new)

    _base_repr = _repr_

    def quotient(self, I, check=True):
        """
        Create the quotient of this algebra by a two-sided ideal ``I``.

        INPUT:

        - ``I`` -- a two-sided homogeneous ideal of this algebra

        - ``check`` -- (default: ``True``) if ``True``, check whether
          ``I`` is generated by homogeneous elements

        EXAMPLES::

            sage: A.<x,y,z,t> = GradedCommutativeAlgebra(GF(5), degrees=(2, 3, 2, 4))
            sage: I = A.ideal([x*t+y^2, x*z - t])
            sage: B = A.quotient(I)
            sage: B
            Graded Commutative Algebra with generators ('x', 'y', 'z', 't') in degrees (2, 3, 2, 4) with relations [x*t, x*z - t] over Finite Field of size 5
            sage: B(x*t)
            0
            sage: B(x*z)
            t
            sage: A.basis(7)
            [y*t, y*z^2, x*y*z, x^2*y]
            sage: B.basis(7)
            [y*t, y*z^2, x^2*y]
        """
        if check and any(not i.is_homogeneous() for i in I.gens()):
            raise ValueError("The ideal must be homogeneous")
        NCR = self.cover_ring()
        gens1 = list(self.defining_ideal().gens())
        gens2 = [i.lift() for i in I.gens()]
        gens = [g for g in gens1 + gens2 if g != NCR.zero()]
        J = NCR.ideal(gens, side='twosided')
        return GCAlgebra_multigraded(self.base_ring(), self._names,
                                     self._degrees_multi, NCR, J)

    def _coerce_map_from_(self, other):
        r"""
        Returns ``True`` if there is a coercion map from ``R`` to ``self``.

        EXAMPLES::

            sage: A.<a,b,c> = GradedCommutativeAlgebra(QQ, degrees=((1,0), (0, 1), (0,2)))
            sage: B = A.cdg_algebra({a: c})
            sage: B._coerce_map_from_(A)
            True
            sage: B._coerce_map_from_(QQ)
            True
            sage: B._coerce_map_from_(GF(3))
            False
        """
        if isinstance(other, GCAlgebra_multigraded):
            if self._degrees_multi != other._degrees_multi:
                return False
        elif isinstance(other, GCAlgebra): # Not multigraded
            return False
        return super(GCAlgebra_multigraded, self)._coerce_map_from_(other)

    def basis(self, n, total=False):
        """
        Basis in degree ``n``.

        - ``n`` -- degree or integer
        - ``total`` (optional, default False) -- if True, return the
          basis in total degree ``n``.

        If ``n`` is an integer rather than a multi-index, then the
        total degree is used in that case as well.

        EXAMPLES::

            sage: A.<a,b,c> = GradedCommutativeAlgebra(GF(2), degrees=((1,0), (0,1), (1,1)))
            sage: A.basis((1,1))
            [c, a*b]
            sage: A.basis(2, total=True)
            [c, b^2, a*b, a^2]

        Since 2 is a not a multi-index, we don't need to specify ``total=True``::

            sage: A.basis(2)
            [c, b^2, a*b, a^2]

        If ``total==True``, then ``n`` can still be a tuple, list,
        etc., and its total degree is used instead::

            sage: A.basis((1,1), total=True)
            [c, b^2, a*b, a^2]
        """
        tot_basis = GCAlgebra.basis(self, total_degree(n))
        if total or n in ZZ:
            return tot_basis
        G = AdditiveAbelianGroup([0] * self._grading_rank)
        n = G(vector(n))
        return [b for b in tot_basis if b.degree() == n]

    def differential(self, diff):
        """
        Construct a differential on ``self``.

        INPUT:

        - ``diff`` -- a dictionary defining a differential

        The keys of the dictionary are generators of the algebra, and
        the associated values are their targets under the
        differential. Any generators which are not specified are
        assumed to have zero differential.

        EXAMPLES::

            sage: A.<a,b,c> = GradedCommutativeAlgebra(QQ, degrees=((1,0), (0, 1), (0,2)))
            sage: A.differential({a: c})
            Differential of Graded Commutative Algebra with generators ('a', 'b', 'c') in degrees ((1, 0), (0, 1), (0, 2)) over Rational Field
              Defn: a --> c
                    b --> 0
                    c --> 0
        """
        return Differential_multigraded(self, diff)

    def cdg_algebra(self, differential):
        r"""
        Construct a differential graded commutative algebra from ``self``
        by specifying a differential.

        INPUT:

        - ``differential`` -- a dictionary defining a differential or
          a map defining a valid differential

        The keys of the dictionary are generators of the algebra, and
        the associated values are their targets under the
        differential. Any generators which are not specified are
        assumed to have zero differential. Alternatively, the
        differential can be defined using the :meth:`differential`
        method; see below for an example.

        .. SEEALSO::

            :meth:`differential`

        EXAMPLES::

            sage: A.<a,b,c> = GradedCommutativeAlgebra(QQ, degrees=((1,0), (0, 1), (0,2)))
            sage: A.cdg_algebra({a: c})
            Commutative Differential Graded Algebra with generators ('a', 'b', 'c') in degrees ((1, 0), (0, 1), (0, 2)) over Rational Field with differential:
               a --> c
               b --> 0
               c --> 0
            sage: d = A.differential({a: c})
            sage: A.cdg_algebra(d)
            Commutative Differential Graded Algebra with generators ('a', 'b', 'c') in degrees ((1, 0), (0, 1), (0, 2)) over Rational Field with differential:
               a --> c
               b --> 0
               c --> 0
        """
        return DifferentialGCAlgebra_multigraded(self, differential)

    class Element(GCAlgebra.Element):
        def degree(self, total=False):
            """
            Return the degree of this element.

            INPUT:

            - ``total`` -- if ``True``, return the total degree, an
              integer; otherwise, return the degree as an element of
              an additive free abelian group

            If not requesting the total degree, raise an error if the
            element is not homogeneous.

            EXAMPLES::

                sage: A.<a,b,c> = GradedCommutativeAlgebra(GF(2), degrees=((1,0), (0,1), (1,1)))
                sage: (a**2*b).degree()
                (2, 1)
                sage: (a**2*b).degree(total=True)
                3
                sage: (a**2*b + c).degree()
                Traceback (most recent call last):
                ...
                ValueError: This element is not homogeneous
                sage: (a**2*b + c).degree(total=True)
                3
                sage: A(0).degree()
                Traceback (most recent call last):
                ...
                ValueError: The zero element does not have a well-defined degree
            """
            if total:
                return GCAlgebra.Element.degree(self)
            if self.is_zero():
                raise ValueError("The zero element does not have a well-defined degree")
            degrees = self.parent()._degrees_multi
            n = self.parent().ngens()
            exps = self.lift().dict().keys()
            l = [sum(exp[i] * degrees[i] for i in range(n)) for exp in exps]
            if len(set(l)) == 1:
                return l[0]
            else:
                raise ValueError('This element is not homogeneous')

###########################################################
## Differential algebras

class DifferentialGCAlgebra(GCAlgebra):
    """
    A commutative differential graded algebra.

    INPUT:

    - ``A`` -- a graded commutative algebra; that is, an instance
      of :class:`GCAlgebra`

    - ``differential`` -- a differential

    As described in the module-level documentation, these are graded
    algebras for which oddly graded elements anticommute and evenly
    graded elements commute, and on which there is a graded
    differential of degree 1.

    These algebras should be graded over the integers; multi-graded
    algebras should be constructed using
    :class:`DifferentialGCAlgebra_multigraded` instead.

    Note that a natural way to construct these is to use the
    :func:`GradedCommutativeAlgebra` function and the
    :meth:`GCAlgebra.cdg_algebra` method.

    EXAMPLES::

        sage: A.<x,y,z,t> = GradedCommutativeAlgebra(QQ, degrees=(3, 2, 2, 3))
        sage: A.cdg_algebra({x: y*z})
        Commutative Differential Graded Algebra with generators ('x', 'y', 'z', 't') in degrees (3, 2, 2, 3) over Rational Field with differential:
            x --> y*z
            y --> 0
            z --> 0
            t --> 0

    Alternatively, starting with :func:`GradedCommutativeAlgebra`::

        sage: A.<x,y,z,t> = GradedCommutativeAlgebra(QQ, degrees=(3, 2, 2, 3))
        sage: A.cdg_algebra(differential={x: y*z})
        Commutative Differential Graded Algebra with generators ('x', 'y', 'z', 't') in degrees (3, 2, 2, 3) over Rational Field with differential:
            x --> y*z
            y --> 0
            z --> 0
            t --> 0

    See the function :func:`GradedCommutativeAlgebra` for more examples.
    """
    @staticmethod
    def __classcall__(cls, A, differential):
        """
        Normalize input to ensure a unique representation.

        EXAMPLES::

            sage: A.<a,b,c> = GradedCommutativeAlgebra(QQ, degrees=(1,1,1))
            sage: D1 = A.cdg_algebra({a: b*c, b: a*c})
            sage: D2 = A.cdg_algebra(D1.differential())
            sage: D1 is D2
            True
            sage: from sage.algebras.commutative_dga import DifferentialGCAlgebra
            sage: D1 is DifferentialGCAlgebra(A, {a: b*c, b: a*c, c: 0})
            True
        """
        if not isinstance(differential, Differential):
            differential = A.differential(differential)
        elif differential.parent() != A:
            differential = Differential(A, differential._dic_)
        return super(GCAlgebra, cls).__classcall__(cls, A, differential)

    def __init__(self, A, differential):
        """
        Initialize ``self``

        INPUT:

        - ``A`` -- a graded commutative algebra

        - ``differential`` -- a differential

        EXAMPLES::

            sage: A.<x,y,z,t> = GradedCommutativeAlgebra(QQ, degrees=(3, 2, 2, 3))
            sage: D = A.cdg_algebra({x: y*z})
            sage: TestSuite(D).run()

        The degree of the differential must be 1::

            sage: A.<a,b,c> = GradedCommutativeAlgebra(QQ, degrees=(1,1,1))
            sage: A.cdg_algebra({a: a*b*c})
            Traceback (most recent call last):
            ...
            ValueError: The given dictionary does not determine a degree 1 map

        The differential composed with itself must be zero::

            sage: A.<a,b,c> = GradedCommutativeAlgebra(QQ, degrees=(1,2,3))
            sage: A.cdg_algebra({a:b, b:c})
            Traceback (most recent call last):
            ...
            ValueError: The given dictionary does not determine a valid differential
        """
        GCAlgebra.__init__(self, A.base(), names=A._names,
                           degrees=A._degrees,
                           R=A.cover_ring(),
                           I=A.defining_ideal())
        self._differential = Differential(self, differential._dic_)

    def graded_commutative_algebra(self):
        """
        Return the base graded commutative algebra of ``self``.

        EXAMPLES::

            sage: A.<x,y,z,t> = GradedCommutativeAlgebra(QQ, degrees=(3, 2, 2, 3))
            sage: D = A.cdg_algebra({x: y*z})
            sage: D.graded_commutative_algebra() == A
            True
        """
        return GCAlgebra(self.base(), names=self._names, degrees=self._degrees,
                         R=self.cover_ring(), I=self.defining_ideal())

    def _base_repr(self):
        """
        Return the base string representation of ``self``.

        EXAMPLES::

            sage: A.<x,y,z,t> = GradedCommutativeAlgebra(QQ, degrees=[3, 4, 2, 1])
            sage: A.cdg_algebra({x:y, t:z})._base_repr()
            "Commutative Differential Graded Algebra with generators ('x', 'y', 'z', 't') in degrees (3, 4, 2, 1) over Rational Field"
        """
        return GCAlgebra._repr_(self).replace('Graded Commutative', 'Commutative Differential Graded')

    def _repr_(self):
        """
        EXAMPLES::

            sage: A.<x,y,z,t> = GradedCommutativeAlgebra(QQ, degrees=[3, 4, 2, 1])
            sage: A.cdg_algebra({x:y, t:z})
            Commutative Differential Graded Algebra with generators ('x', 'y', 'z', 't') in degrees (3, 4, 2, 1) over Rational Field with differential:
               x --> y
               y --> 0
               z --> 0
               t --> z
        """
        d = self._differential._repr_defn().replace('\n', '\n   ')
        return self._base_repr() + " with differential:{}".format('\n   ' + d)

    def quotient(self, I, check=True):
        """
        Create the quotient of this algebra by a two-sided ideal ``I``.

        INPUT:

        - ``I`` -- a two-sided homogeneous ideal of this algebra

        - ``check`` -- (default: ``True``) if ``True``, check whether
          ``I`` is generated by homogeneous elements

        EXAMPLES::

            sage: A.<x,y,z> = GradedCommutativeAlgebra(QQ, degrees=(2,1,1))
            sage: B = A.cdg_algebra({y:y*z, z: y*z})
            sage: B.inject_variables()
            Defining x, y, z
            sage: I = B.ideal([x*y])
            sage: C = B.quotient(I)
            sage: (x*y).differential()
            x*y*z
            sage: C((x*y).differential())
            0
            sage: C(x*y)
            0

        It is checked that the differential maps the ideal into itself, to make
        sure that the quotient inherits a differential structure::

            sage: A.<x,y,z> = GradedCommutativeAlgebra(QQ, degrees=(2,2,1))
            sage: B = A.cdg_algebra({z:y})
            sage: B.quotient(B.ideal(y*z))
            Traceback (most recent call last):
            ...
            ValueError: The differential does not preserve the ideal
            sage: B.quotient(B.ideal(z))
            Traceback (most recent call last):
            ...
            ValueError: The differential does not preserve the ideal
        """
        J = self.ideal(I)
        AQ = GCAlgebra.quotient(self, J, check)
        for g in I.gens():
            if not AQ(g.differential()).is_zero():
                raise ValueError("The differential does not preserve the ideal")
        dic = {AQ(a): AQ(a.differential()) for a in self.gens()}
        return AQ.cdg_algebra(dic)

    def differential(self, x=None):
        r"""
        The differential of ``self``.

        This returns a map, and so it may be evaluated on elements of
        this algebra.

        EXAMPLES::

            sage: A.<x,y,z> = GradedCommutativeAlgebra(QQ, degrees=(2,1,1))
            sage: B = A.cdg_algebra({y:y*z, z: y*z})
            sage: d = B.differential(); d
            Differential of Commutative Differential Graded Algebra with generators ('x', 'y', 'z') in degrees (2, 1, 1) over Rational Field
              Defn: x --> 0
                    y --> y*z
                    z --> y*z
            sage: d(y)
            y*z
        """
        return self._differential

    def coboundaries(self, n):
        """
        The ``n``-th coboundary group of the algebra.

        This is a vector space over the base field `F`, and it is
        returned as a subspace of the vector space `F^d`, where the
        ``n``-th homogeneous component has dimension `d`.

        INPUT:

        - ``n`` -- degree

        EXAMPLES::

            sage: A.<x,y,z> = GradedCommutativeAlgebra(QQ, degrees=(1,1,2))
            sage: B = A.cdg_algebra(differential={z: x*z})
            sage: B.coboundaries(2)
            Vector space of degree 2 and dimension 0 over Rational Field
            Basis matrix:
            []
            sage: B.coboundaries(3)
            Vector space of degree 2 and dimension 1 over Rational Field
            Basis matrix:
            [0 1]
            sage: B.basis(3)
            [y*z, x*z]
        """
        return self._differential.coboundaries(n)

    def cocycles(self, n):
        """
        The ``n``-th cocycle group of the algebra.

        This is a vector space over the base field `F`, and it is
        returned as a subspace of the vector space `F^d`, where the
        ``n``-th homogeneous component has dimension `d`.

        INPUT:

        - ``n`` -- degree

        EXAMPLES::

            sage: A.<x,y,z> = GradedCommutativeAlgebra(QQ, degrees=(1,1,2))
            sage: B = A.cdg_algebra(differential={z: x*z})
            sage: B.cocycles(2)
            Vector space of degree 2 and dimension 1 over Rational Field
            Basis matrix:
            [1 0]
            sage: B.basis(2)
            [x*y, z]
        """
        return self._differential.cocycles(n)

    def cohomology_raw(self, n):
        """
        The ``n``-th cohomology group of ``self``.

        This is a vector space over the base ring, and it is returned
        as the quotient cocycles/coboundaries.

        INPUT:

        - ``n`` -- degree

        EXAMPLES::

            sage: A.<x,y,z,t> = GradedCommutativeAlgebra(QQ, degrees = (2,3,2,4))
            sage: B = A.cdg_algebra({t: x*y, x: y, z: y})
            sage: B.cohomology_raw(4)
            Vector space quotient V/W of dimension 2 over Rational Field where
            V: Vector space of degree 4 and dimension 2 over Rational Field
            Basis matrix:
            [   1    0    0 -1/2]
            [   0    1   -2    1]
            W: Vector space of degree 4 and dimension 0 over Rational Field
            Basis matrix:
            []

        Compare to :meth:`cohomology`::

            sage: B.cohomology(4)
            Free module generated by {[-1/2*x^2 + t], [x^2 - 2*x*z + z^2]} over Rational Field
        """
        return self._differential.cohomology_raw(n)

    def cohomology(self, n):
        """
        The ``n``-th cohomology group of ``self``.

        This is a vector space over the base ring, defined as the
        quotient cocycles/coboundaries. The elements of the quotient
        are lifted to the vector space of cocycles, and this is
        described in terms of those lifts.

        INPUT:

        - ``n`` -- degree

        EXAMPLES::

            sage: A.<a,b,c,d,e> = GradedCommutativeAlgebra(QQ, degrees=(1,1,1,1,1))
            sage: B = A.cdg_algebra({d: a*b, e: b*c})
            sage: B.cohomology(2)
            Free module generated by {[c*e], [c*d - a*e], [b*e], [b*d], [a*d], [a*c]} over Rational Field

        Compare to :meth:`cohomology_raw`::

            sage: B.cohomology_raw(2)
            Vector space quotient V/W of dimension 6 over Rational Field where
            V: Vector space of degree 10 and dimension 8 over Rational Field
            Basis matrix:
            [ 0  1  0  0  0  0  0  0  0  0]
            [ 0  0  1  0  0  0 -1  0  0  0]
            [ 0  0  0  1  0  0  0  0  0  0]
            [ 0  0  0  0  1  0  0  0  0  0]
            [ 0  0  0  0  0  1  0  0  0  0]
            [ 0  0  0  0  0  0  0  1  0  0]
            [ 0  0  0  0  0  0  0  0  1  0]
            [ 0  0  0  0  0  0  0  0  0  1]
            W: Vector space of degree 10 and dimension 2 over Rational Field
            Basis matrix:
            [0 0 0 0 0 1 0 0 0 0]
            [0 0 0 0 0 0 0 0 0 1]
        """
        return self._differential.cohomology(n)

    class Element(GCAlgebra.Element):
        def differential(self):
            """
            The differential on this element.

            EXAMPLES::

                sage: A.<x,y,z,t> = GradedCommutativeAlgebra(QQ, degrees = (2, 3, 2, 4))
                sage: B = A.cdg_algebra({t: x*y, x: y, z: y})
                sage: B.inject_variables()
                Defining x, y, z, t
                sage: x.differential()
                y
                sage: (-1/2 * x^2 + t).differential()
                0
            """
            return self.parent().differential()(self)

        def is_coboundary(self):
            """
            Return ``True`` if ``self`` is a coboundary and ``False``
            otherwise.

            This raises an error if the element is not homogeneous.

            EXAMPLES::

                sage: A.<a,b,c> = GradedCommutativeAlgebra(QQ, degrees=(1,2,2))
                sage: B = A.cdg_algebra(differential={b: a*c})
                sage: x,y,z = B.gens()
                sage: x.is_coboundary()
                False
                sage: (x*z).is_coboundary()
                True
                sage: (x*z+x*y).is_coboundary()
                False
                sage: (x*z+y**2).is_coboundary()
                Traceback (most recent call last):
                ...
                ValueError: This element is not homogeneous
            """
            try:
                assert self.is_homogeneous()
            except AssertionError:
                raise ValueError('This element is not homogeneous')
            # To avoid taking the degree of 0, we special-case it.
            if self.is_zero():
                return True
            v = vector(self.basis_coefficients())
            return v in self.parent().coboundaries(self.degree())

        def is_cohomologous_to(self, other):
            """
            Return ``True`` if ``self`` is cohomologous to ``other``
            and ``False`` otherwise.

            INPUT:

            - ``other`` -- another element of this algebra

            EXAMPLES::

                sage: A.<a,b,c,d> = GradedCommutativeAlgebra(QQ, degrees=(1,1,1,1))
                sage: B = A.cdg_algebra(differential={a:b*c-c*d})
                sage: w, x, y, z = B.gens()
                sage: (x*y).is_cohomologous_to(y*z)
                True
                sage: (x*y).is_cohomologous_to(x*z)
                False
                sage: (x*y).is_cohomologous_to(x*y)
                True

            Two elements whose difference is not homogeneous are
            cohomologous if and only if they are both coboundaries::

                sage: w.is_cohomologous_to(y*z)
                False
                sage: (x*y-y*z).is_cohomologous_to(x*y*z)
                True
                sage: (x*y*z).is_cohomologous_to(0) # make sure 0 works
                True

            """
            if other.is_zero():
                return self.is_coboundary()
            if (not isinstance(other, DifferentialGCAlgebra.Element)
                or self.parent() is not other.parent()):
                raise ValueError('The element {} does not lie in this DGA'.format(other))
            if (self - other).is_homogeneous():
                return (self - other).is_coboundary()
            else:
                return (self.is_coboundary() and other.is_coboundary())

class DifferentialGCAlgebra_multigraded(DifferentialGCAlgebra, GCAlgebra_multigraded):
    """
    A commutative differential multi-graded algebras.

    INPUT:

    - ``A`` -- a commutative multi-graded algebra

    - ``differential`` -- a differential

    EXAMPLES::

        sage: A.<a,b,c> = GradedCommutativeAlgebra(QQ, degrees=((1,0), (0, 1), (0,2)))
        sage: B = A.cdg_algebra(differential={a: c})
        sage: B.basis((1,0))
        [a]
        sage: B.basis(1, total=True)
        [b, a]
        sage: B.cohomology((1, 0))
        Free module generated by {} over Rational Field
        sage: B.cohomology(1, total=True)
        Free module generated by {[b]} over Rational Field
    """
    def __init__(self, A, differential):
        """
        Initialize ``self``.

        INPUT:

        - ``A`` -- a multi-graded commutative algebra
        - ``differential`` -- a differential

        EXAMPLES::

            sage: A.<a,b,c> = GradedCommutativeAlgebra(QQ, degrees=((1,0), (0, 1), (0,2)))
            sage: B = A.cdg_algebra(differential={a: c})

        Trying to define a differential which is not multi-graded::

            sage: A.<t,x,y,z> = GradedCommutativeAlgebra(QQ, degrees=((1,0),(1,0),(2,0),(0,2)))
            sage: B = A.cdg_algebra(differential={x:y}) # good
            sage: B = A.cdg_algebra(differential={t:z}) # good
            sage: B = A.cdg_algebra(differential={x:y, t:z}) # bad
            Traceback (most recent call last):
            ...
            ValueError: The differential does not have a well-defined degree
        """
        GCAlgebra_multigraded.__init__(self, A.base(), names=A._names,
                                       degrees=A._degrees_multi,
                                       R=A.cover_ring(),
                                       I=A.defining_ideal())
        self._differential = Differential_multigraded(self, differential._dic_)

    def _base_repr(self):
        """
        Return the base string representation of ``self``.

        EXAMPLES::

            sage: A.<a,b,c> = GradedCommutativeAlgebra(QQ, degrees=((1,0), (0, 1), (0,2)))
            sage: A.cdg_algebra(differential={a: c})._base_repr()
            "Commutative Differential Graded Algebra with generators ('a', 'b', 'c') in degrees ((1, 0), (0, 1), (0, 2)) over Rational Field"
        """
        s = DifferentialGCAlgebra._base_repr(self)
        old = '{}'.format(self._degrees)
        new = '{}'.format(self._degrees_multi)
        return s.replace(old, new)

    def coboundaries(self, n, total=False):
        """
        The ``n``-th coboundary group of the algebra.

        This is a vector space over the base field `F`, and it is
        returned as a subspace of the vector space `F^d`, where the
        ``n``-th homogeneous component has dimension `d`.

        INPUT:

        - ``n`` -- degree
        - ``total`` (default ``False``) -- if ``True``, return the
          coboundaries in total degree ``n``

        If ``n`` is an integer rather than a multi-index, then the
        total degree is used in that case as well.

        EXAMPLES::

            sage: A.<a,b,c> = GradedCommutativeAlgebra(QQ, degrees=((1,0), (0, 1), (0,2)))
            sage: B = A.cdg_algebra(differential={a: c})
            sage: B.coboundaries((0,2))
            Vector space of degree 1 and dimension 1 over Rational Field
            Basis matrix:
            [1]
            sage: B.coboundaries(2)
            Vector space of degree 2 and dimension 1 over Rational Field
            Basis matrix:
            [0 1]
        """
        return self._differential.coboundaries(n, total)

    def cocycles(self, n, total=False):
        r"""
        The ``n``-th cocycle group of the algebra.

        This is a vector space over the base field `F`, and it is
        returned as a subspace of the vector space `F^d`, where the
        ``n``-th homogeneous component has dimension `d`.

        INPUT:

        - ``n`` -- degree
        - ``total`` -- (default: ``False``) if ``True``, return the
          cocycles in total degree ``n``

        If ``n`` is an integer rather than a multi-index, then the
        total degree is used in that case as well.

        EXAMPLES::

            sage: A.<a,b,c> = GradedCommutativeAlgebra(QQ, degrees=((1,0), (0, 1), (0,2)))
            sage: B = A.cdg_algebra(differential={a: c})
            sage: B.cocycles((0,1))
            Vector space of degree 1 and dimension 1 over Rational Field
            Basis matrix:
            [1]
            sage: B.cocycles((0,1), total=True)
            Vector space of degree 2 and dimension 1 over Rational Field
            Basis matrix:
            [1 0]
        """
        return self._differential.cocycles(n, total)

    def cohomology_raw(self, n, total=False):
        """
        The ``n``-th cohomology group of the algebra.

        This is a vector space over the base ring, and it is returned
        as the quotient cocycles/coboundaries.

        Compare to :meth:`cohomology`.

        INPUT:

        - ``n`` -- degree
        - ``total`` -- (default: ``False``) if ``True``, return the
          cohomology in total degree ``n``

        If ``n`` is an integer rather than a multi-index, then the
        total degree is used in that case as well.

        EXAMPLES::

            sage: A.<a,b,c> = GradedCommutativeAlgebra(QQ, degrees=((1,0), (0, 1), (0,2)))
            sage: B = A.cdg_algebra(differential={a: c})
            sage: B.cohomology_raw((0,2))
            Vector space quotient V/W of dimension 0 over Rational Field where
            V: Vector space of degree 1 and dimension 1 over Rational Field
            Basis matrix:
            [1]
            W: Vector space of degree 1 and dimension 1 over Rational Field
            Basis matrix:
            [1]

            sage: B.cohomology_raw(1)
            Vector space quotient V/W of dimension 1 over Rational Field where
            V: Vector space of degree 2 and dimension 1 over Rational Field
            Basis matrix:
            [1 0]
            W: Vector space of degree 2 and dimension 0 over Rational Field
            Basis matrix:
            []
        """
        return self._differential.cohomology_raw(n, total)

    def cohomology(self, n, total=False):
        """
        The ``n``-th cohomology group of the algebra.

        This is a vector space over the base ring, defined as the
        quotient cocycles/coboundaries. The elements of the quotient
        are lifted to the vector space of cocycles, and this is
        described in terms of those lifts.

        Compare to :meth:`cohomology_raw`.

        INPUT:

        - ``n`` -- degree
        - ``total`` -- (default: ``False``) if ``True``, return the
          cohomology in total degree ``n``

        If ``n`` is an integer rather than a multi-index, then the
        total degree is used in that case as well.

        EXAMPLES::

            sage: A.<a,b,c> = GradedCommutativeAlgebra(QQ, degrees=((1,0), (0, 1), (0,2)))
            sage: B = A.cdg_algebra(differential={a: c})
            sage: B.cohomology((0,2))
            Free module generated by {} over Rational Field

            sage: B.cohomology(1)
            Free module generated by {[b]} over Rational Field
        """
        return self._differential.cohomology(n, total)

    class Element(GCAlgebra_multigraded.Element, DifferentialGCAlgebra.Element):
        """
        Element class of a commutative differential multi-graded algebra.
        """

################################################
# Main entry point

def GradedCommutativeAlgebra(ring, names=None, degrees=None, relations=None):
    r"""
    A graded commutative algebra.

    INPUT:

    There are two ways to call this. The first way defines a free
    graded commutative algebra:

    - ``ring`` -- the base field over which to work

    - ``names`` -- names of the generators. You may also use Sage's
      ``A.<x,y,...> = ...`` syntax to define the names. If no names
      are specified, the generators are named ``x0``, ``x1``, ...

    - ``degrees`` -- degrees of the generators; if this is omitted,
      the degree of each generator is 1, and if both ``names`` and
      ``degrees`` are omitted, an error is raised

    Once such an algebra has been defined, one can use its associated
    methods to take a quotient, impose a differential, etc. See the
    examples below.

    The second way takes a graded commutative algebra and imposes
    relations:

    - ``ring`` -- a graded commutative algebra

    - ``relations`` -- a list or tuple of elements of ``ring``

    EXAMPLES:

    Defining a graded commutative algebra::

        sage: GradedCommutativeAlgebra(QQ, 'x, y, z')
        Graded Commutative Algebra with generators ('x', 'y', 'z') in degrees (1, 1, 1) over Rational Field
        sage: GradedCommutativeAlgebra(QQ, degrees=(2, 3, 4))
        Graded Commutative Algebra with generators ('x0', 'x1', 'x2') in degrees (2, 3, 4) over Rational Field

    As usual in Sage, the ``A.<...>`` notation defines both the
    algebra and the generator names::

        sage: A.<x,y,z> = GradedCommutativeAlgebra(QQ, degrees=(1, 2, 1))
        sage: x^2
        0
        sage: z*x # Odd classes anticommute.
        -x*z
        sage: z*y # y is central since it is in degree 2.
        y*z
        sage: (x*y**3*z).degree()
        8
        sage: A.basis(3) # basis of homogeneous degree 3 elements
        [y*z, x*y]

    Defining a quotient::

        sage: I = A.ideal(x*y)
        sage: AQ = A.quotient(I)
        sage: AQ
        Graded Commutative Algebra with generators ('x', 'y', 'z') in degrees (1, 2, 1) with relations [x*y] over Rational Field
        sage: AQ.basis(3)
        [y*z]

    Note that ``AQ`` has no specified differential. This is reflected in
    its print representation: ``AQ`` is described as a "graded commutative
    algebra" -- the word "differential" is missing. Also, it has no
    default ``differential``::

        sage: AQ.differential()
        Traceback (most recent call last):
        ...
        TypeError: differential() takes exactly 2 arguments (1 given)

    Now we add a differential to ``AQ``::

        sage: B = AQ.cdg_algebra({y:y*z})
        sage: B
        Commutative Differential Graded Algebra with generators ('x', 'y', 'z') in degrees (1, 2, 1) with relations [x*y] over Rational Field with differential:
            x --> 0
            y --> y*z
            z --> 0
        sage: B.differential()
        Differential of Commutative Differential Graded Algebra with generators ('x', 'y', 'z') in degrees (1, 2, 1) with relations [x*y] over Rational Field
          Defn: x --> 0
                y --> y*z
                z --> 0
        sage: B.cohomology(1)
        Free module generated by {[z], [x]} over Rational Field
        sage: B.cohomology(2)
        Free module generated by {[x*z]} over Rational Field

    We can construct multi-graded rings as well. We work in characteristic 2
    for a change, so the algebras here are honestly commutative::

        sage: C.<a,b,c,d> = GradedCommutativeAlgebra(GF(2), degrees=((1,0), (1,1), (0,2), (0,3)))
        sage: D = C.cdg_algebra(differential={a:c, b:d})
        sage: D
        Commutative Differential Graded Algebra with generators ('a', 'b', 'c', 'd') in degrees ((1, 0), (1, 1), (0, 2), (0, 3)) over Finite Field of size 2 with differential:
            a --> c
            b --> d
            c --> 0
            d --> 0

    We can examine ``D`` using both total degrees and multidegrees.
    Use tuples, lists, vectors, or elements of additive
    abelian groups to specify degrees::

        sage: D.basis(3) # basis in total degree 3
        [d, a*c, a*b, a^3]
        sage: D.basis((1,2)) # basis in degree (1,2)
        [a*c]
        sage: D.basis([1,2])
        [a*c]
        sage: D.basis(vector([1,2]))
        [a*c]
        sage: G = AdditiveAbelianGroup([0,0]); G
        Additive abelian group isomorphic to Z + Z
        sage: D.basis(G(vector([1,2])))
        [a*c]

    At this point, ``a``, for example, is an element of ``C``. We can
    redefine it so that it is instead an element of ``D`` in several
    ways, for instance using :meth:`gens` method::

        sage: a, b, c, d = D.gens()
        sage: a.differential()
        c

    Or the :meth:`inject_variables` method::

        sage: D.inject_variables()
        Defining a, b, c, d
        sage: (a*b).differential()
        b*c + a*d
        sage: (a*b*c**2).degree()
        (2, 5)

    Degrees are returned as elements of additive abelian groups::

        sage: (a*b*c**2).degree() in G
        True

        sage: (a*b*c**2).degree(total=True)  # total degree
        7
        sage: D.cohomology(4)
        Free module generated by {[b^2], [a^4]} over Finite Field of size 2
        sage: D.cohomology((2,2))
        Free module generated by {[b^2]} over Finite Field of size 2

    TESTS:

    We need to specify either name or degrees::

        sage: GradedCommutativeAlgebra(QQ)
        Traceback (most recent call last):
        ...
        ValueError: You must specify names or degrees
    """
    multi = False
    if degrees:
        try:
            for d in degrees:
                _ = list(d)
            # If the previous line doesn't raise an error, looks multigraded.
            multi = True
        except TypeError:
            pass
    if multi:
        return GCAlgebra_multigraded(ring, names=names, degrees=degrees)
    else:
        return GCAlgebra(ring, names=names, degrees=degrees)

################################################
# Miscellaneous utility classes and functions

class CohomologyClass(SageObject):
    """
    A class for representing cohomology classes.

    This just has ``_repr_`` and ``_latex_`` methods which put
    brackets around the object's name.

    EXAMPLES::

        sage: from sage.algebras.commutative_dga import CohomologyClass
        sage: CohomologyClass(3)
        [3]
        sage: A.<x,y,z,t> = GradedCommutativeAlgebra(QQ, degrees = (2,3,3,1))
        sage: CohomologyClass(x^2+2*y*z)
        [2*y*z + x^2]
    """
    def __init__(self, x):
        """
        EXAMPLES::

            sage: from sage.algebras.commutative_dga import CohomologyClass
            sage: CohomologyClass(x-2)
            [x - 2]
        """
        self._x = x

    def _repr_(self):
        """
        EXAMPLES::

            sage: from sage.algebras.commutative_dga import CohomologyClass
            sage: CohomologyClass(sin)
            [sin]
        """
        return '[{}]'.format(self._x)

    def _latex_(self):
        r"""
        EXAMPLES::

            sage: from sage.algebras.commutative_dga import CohomologyClass
            sage: latex(CohomologyClass(sin))
            \left[ \sin \right]
            sage: latex(CohomologyClass(x^2))
            \left[ x^{2} \right]
        """
        from sage.misc.latex import latex
        return '\\left[ {} \\right]'.format(latex(self._x))

    def representative(self):
        """
        Return the representative of ``self``.

        EXAMPLES::

            sage: from sage.algebras.commutative_dga import CohomologyClass
            sage: x = CohomologyClass(sin)
            sage: x.representative() == sin
            True
        """
        return self._x

def exterior_algebra_basis(n, degrees):
    """
    Basis of an exterior algebra in degree ``n``, where the
    generators are in degrees ``degrees``.

    INPUT:

    - ``n`` - integer
    - ``degrees`` - iterable of integers

    Return list of lists, each list representing exponents for the
    corresponding generators. (So each list consists of 0's and 1's.)

    EXAMPLES::

        sage: from sage.algebras.commutative_dga import exterior_algebra_basis
        sage: exterior_algebra_basis(1, (1,3,1))
        [[0, 0, 1], [1, 0, 0]]
        sage: exterior_algebra_basis(4, (1,3,1))
        [[0, 1, 1], [1, 1, 0]]
        sage: exterior_algebra_basis(10, (1,5,1,1))
        []
    """
    zeroes = [0]*len(degrees)
    if not degrees:
        if n == 0:
            return [zeroes]
        else:
            return []
    if len(degrees) == 1:
        if n == degrees[0]:
            return [[1]]
        elif n == 0:
            return [zeroes]
        else:
            return []
    result = [[0] + v for
              v in exterior_algebra_basis(n, degrees[1:])]
    if n == 0 and zeroes not in result:
        result += [zeroes]
    d = degrees[0]
    return result + [[1] + v for
                     v in exterior_algebra_basis(n-d, degrees[1:])]

def total_degree(deg):
    """
    Total degree of ``deg``.

    INPUT:

    - ``deg`` - an element of a free abelian group.

    In fact, ``deg`` could be an integer, a Python int, a list, a
    tuple, a vector, etc. This function returns the sum of the
    components of ``deg``.

    EXAMPLES::

        sage: from sage.algebras.commutative_dga import total_degree
        sage: total_degree(12)
        12
        sage: total_degree(range(5))
        10
        sage: total_degree(vector(range(5)))
        10
        sage: G = AdditiveAbelianGroup((0,0))
        sage: x = G.gen(0); y = G.gen(1)
        sage: 3*x+4*y
        (3, 4)
        sage: total_degree(3*x+4*y)
        7
    """
    if deg in ZZ:
        return deg
    return sum(deg)
