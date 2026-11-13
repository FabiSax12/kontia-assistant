export function colones(n: number | string): string {
  return "₡" + Math.round(Number(n)).toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ")
}
