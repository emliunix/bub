# How case typed

the rule from the paper:
$$
\cfrac{
\begin{aligned}
& \Gamma \vdash_{tm} e:T\ \overline{\tau'}\\
& \Gamma \vdash_{ty} \tau:\star \\
& \overline{K_i} \text{ are exhaustive for } T \\
& \text{for each } i\\
    & \qquad \begin{aligned}
    & K_i:\forall\overline{a:k}.\ \forall\Delta_i.\ \overline{\sigma_i}\rightarrow(T\ \overline{a})\in\Gamma \\
    & \cfrac
        {\Delta_i'=\Delta_i[\overline{\tau'/a}]}
        {\sigma_i'=\sigma[\overline{\tau'}/\overline{a}]} \\
    & \Gamma,\Delta_i',\overline{x_i:\sigma_i'}\vdash_{tm} u_i:\tau
    \end{aligned}
\end{aligned}
}
{\Gamma \vdash_{tm} \text{case } e \text{ of } \overline{K_i\Delta_i'\overline{x_i:\sigma_i'}\rightarrow u_i}:\tau}
\text{T\_Case}
$$

Let's simplify it, remove telescopes and kinds:

$$
\cfrac{
\begin{aligned}
& \Gamma \vdash_{tm} e:T\ \overline{\tau'}\\
& \overline{K_i} \text{ are exhaustive for } T \\
& \text{for each } i\\
    & \qquad \begin{aligned}
    & K_i:\forall\overline{a}.\ \overline{\sigma_i}\rightarrow(T\ \overline{a})\in\Gamma \\
    & \Gamma,\overline{x_i:\sigma_i'}\vdash_{tm} u_i:\tau
    \end{aligned}
\end{aligned}
}
{\Gamma \vdash_{tm} \text{case } e \text{ of } \overline{K_i\overline{x_i:\sigma_i'}\rightarrow u_i}:\tau}
\text{T\_Case}
$$
