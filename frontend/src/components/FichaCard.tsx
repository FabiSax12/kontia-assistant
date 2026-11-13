import { BookOpen, ExternalLink } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableRow } from "@/components/ui/table"
import type { Calculo, Ficha } from "@/lib/api"
import { colones } from "@/lib/format"

type Row = [label: string, value: string, strong?: boolean]

function calculoRows(c: Calculo): Row[] {
  const d = c.datos
  if (c.tool === "calcular_aguinaldo") {
    const extra = d.dias_residuales ? ` y ${d.dias_residuales} días` : ""
    return [
      ["Tiempo contado", `${d.meses_contados} meses${extra}`],
      ["Periodo", `${d.periodo_inicio} al ${d.periodo_fin}`],
      ["Fecha límite", String(d.fecha_limite)],
      ["Aguinaldo", colones(d.monto), true],
    ]
  }
  if (c.tool === "calcular_cargas_sociales") {
    return [
      ["Salario bruto", colones(d.salario_bruto)],
      [`Cuota patronal (${(Number(d.tasa_patronal) * 100).toFixed(2)} %)`, colones(d.patronal)],
      [`Cuota obrera (${(Number(d.tasa_obrera) * 100).toFixed(2)} %)`, colones(d.obrera)],
      ["Neto antes de renta", colones(d.neto_antes_renta), true],
    ]
  }
  if (c.tool === "calcular_costo_empleado") {
    return [
      ["Salario del periodo", colones(d.salario_periodo)],
      ["Aguinaldo", colones(d.aguinaldo)],
      ["CCSS patronal", colones(d.ccss_patronal)],
      ["INS", colones(d.ins)],
      ["Costo total", colones(d.costo_total), true],
    ]
  }
  return []
}

export function FichaCard({ ficha, calculo }: { ficha: Ficha; calculo?: Calculo | null }) {
  const rows = calculo ? calculoRows(calculo) : []
  const isLink = /^https?:\/\//.test(ficha.fuente)
  return (
    <Card size="sm" className="w-full max-w-md">
      <CardHeader>
        <CardTitle className="flex items-start gap-2 text-sm">
          <BookOpen className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
          <span>Ficha: {ficha.titulo}</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-xs text-muted-foreground">
        <div>Revisada el {ficha.fecha_revision}</div>
        {isLink ? (
          <a
            href={ficha.fuente}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 break-all text-primary underline-offset-2 hover:underline"
          >
            {ficha.fuente}
            <ExternalLink className="size-3 shrink-0" aria-hidden />
          </a>
        ) : (
          <div>Fuente oficial: {ficha.fuente}</div>
        )}
        {rows.length > 0 && (
          <Table className="text-foreground">
            <TableBody>
              {rows.map(([label, value, strong]) => (
                <TableRow key={label}>
                  <TableCell className="whitespace-normal px-0 text-muted-foreground">
                    {label}
                  </TableCell>
                  <TableCell
                    className={"px-0 text-right " + (strong ? "font-semibold" : "font-medium")}
                  >
                    {value}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  )
}
