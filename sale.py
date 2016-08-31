# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from decimal import Decimal

from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval
from trytond.modules.account_invoice_tree.invoice import ChapterMixin

__all__ = ['Sale', 'SaleLine']


class Sale:
    __metaclass__ = PoolMeta
    __name__ = 'sale.sale'
    lines_tree = fields.Function(fields.One2Many('sale.line', None, 'Lines',
            domain=[
                ('parent', '=', None),
                ]),
        'get_lines_tree', setter='set_lines_tree')

    @classmethod
    def __setup__(cls):
        super(Sale, cls).__setup__()
        if cls.lines.domain:
            cls.lines_tree._field.domain.extend(cls.lines.domain)
        cls.lines_tree._field.states = cls.lines.states
        cls.lines_tree._field.context = cls.lines.context
        cls.lines_tree._field.depends = cls.lines.depends

    def get_lines_tree(self, name):
        return [x.id for x in self.lines if not x.parent]

    @classmethod
    def set_lines_tree(cls, lines, name, value):
        cls.write(lines, {
                'lines': value,
                })

    @classmethod
    def copy(cls, sales, default=None):
        pool = Pool()
        SaleLine = pool.get('sale.line')
        if default is None:
            default = {}
        default['lines'] = []
        new_sales = super(Sale, cls).copy(sales, default=default)
        for sale, new_sale in zip(sales, new_sales):
            new_default = default.copy()
            new_default['sale'] = new_sale.id
            SaleLine.copy(sale.lines_tree, default=new_default)
        return new_sales


class SaleLine(ChapterMixin):
    __metaclass__ = PoolMeta
    __name__ = 'sale.line'
    parent = fields.Many2One('sale.line', 'Parent', select=True,
        ondelete='CASCADE',
        domain=[
            ('sale', '=', Eval('sale')),
            ('type', '=', 'title'),
            ],
        depends=['sale'])
    childs = fields.One2Many('sale.line', 'parent', 'Children',
        domain=[
            ('sale', '=', Eval('sale')),
            ],
        depends=['sale'])

    @classmethod
    def __setup__(cls):
        super(SaleLine, cls).__setup__()
        cls.product.states['readonly'] = False
        cls.quantity.states['readonly'] = False

    def get_amount(self, name):
        if self.parent and (self.type == 'subtotal'
                and self.parent.type == 'title'):
            def get_amount_rec(parent):
                subtotal = Decimal(0)
                for line2 in parent.childs:
                    if line2.childs:
                        subtotal += get_amount_rec(line2)
                    if line2.type == 'line':
                        subtotal += line2.sale.currency.round(
                            Decimal(str(line2.quantity)) * line2.unit_price)
                    elif line2.type == self.type:
                        if self == line2:
                            return subtotal
                        subtotal = Decimal(0)
                return subtotal

            return get_amount_rec(self.parent)
        return super(SaleLine, self).get_amount(name)

    @classmethod
    def get_1st_level_chapters(cls, records):
        for sale in {l.sale for l in records}:
            yield sale.lines_tree

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        default['childs'] = []
        new_lines = []
        for line in lines:
            new_line, = super(SaleLine, cls).copy([line], default)
            new_lines.append(new_line)
            new_default = default.copy()
            new_default['parent'] = new_line.id
            cls.copy(line.childs, default=new_default)
        return new_lines
