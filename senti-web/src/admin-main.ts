import { createApp } from "vue";
import AdminShell from "./admin/AdminShell.vue";
import { router } from "./admin/router";
import "./admin/admin-reset.css";

createApp(AdminShell).use(router).mount("#app");
